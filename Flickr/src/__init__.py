'''
Created on May 27, 2009

@summary: A Plex Media Server plugin that integrates Flickr into the Plex picture container.
@version: 0.1
@author: Ian.G
'''

# Import from Python

import sys
import locale

import socket
import datetime
from math import log, floor, pow
from types import *

# Import the parts of the Plex Media Server Plugin API we need

import re, string, os
from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *

# Import Flickr-related stuff

# Note: This plugin makes use of Beej's python API for Flickr. Sybren Stuvel now maintains this codebase.
# You can find more details about the API at http://stuvel.eu/projects/flickrapi

import flickrapi
from flickrapi.exceptions import *

FLICKR_API_KEY					= "4fc686ef9f76a6c8ba0fd95e4ce0a293"
FLICKR_API_SECRET				= "1a343b9975ce2fdd"
FLICKR_API_CLIENT_NAME 			= "PlexMediaServer-FlickrPlugin-0.1"

# Plugin parameters

PLUGIN_TITLE						= "Flickr"				# The plugin Title
PLUGIN_PREFIX   					= "/photos/flickr"		# The plugin's contextual path within Plex
PLUGIN_HTTP_CACHE_INTERVAL			= 0

# Plugin Icons

PLUGIN_ICON_DEFAULT					= "icon-default.png"
#PLUGIN_ICON_ABOUT					= "icon-about.png"
PLUGIN_ICON_PREFS					= "icon-prefs.png"
PLUGIN_ICON_MORE					= "icon-more.png"

# Plugin Preference Keys

PLUGIN_PREF_USERNAME				= "username"
PLUGIN_PREF_PASSWORD				= "password"
PLUGIN_PREF_SHOW_PRIVATE_ALBUMS		= "showprivatealbums"
PLUGIN_PREF_SHOW_PHOTO_SUMMARY		= "showphotosummary"

# Plugin Artwork

PLUGIN_ARTWORK						= "art-default.jpg"
PLUGIN_ARTWORK_ABOUT				= "art-about.jpg"

# Flickr-related

PAGE_MAX_PHOTOS						= 51

global flickr
global userid
global username

####################################################################################################

def Start():
	
	#reload(sys)
	#sys.setdefaultencoding("utf-8")
	
	Log("default encoding is '%s'" % sys.getdefaultencoding())
	Log("default locale is '%s' '%s'" % locale.getdefaultlocale())
	
	# Register our plugins request handler
	
	Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, PLUGIN_TITLE, PLUGIN_ICON_DEFAULT, PLUGIN_ARTWORK)
	
	# Add in the views our plugin will support
	
	Plugin.AddViewGroup("PhotoStream", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("Sets", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("Tags", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("Contacts", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("Groups", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("Photos", viewMode="Pictures", mediaType="photos")
	
	# Set up our plugin's container
	
	MediaContainer.title1 = PLUGIN_TITLE
	MediaContainer.content = 'Items'
	MediaContainer.viewMode = "InfoList"
	MediaContainer.art = R(PLUGIN_ARTWORK)
	
	# Configure HTTP Cache lifetime
	
	HTTP.SetCacheTime(PLUGIN_HTTP_CACHE_INTERVAL)
	
	# Force preferences to be loaded
	
	Prefs.__load()
	
	# Initialise our Flickr accessor
	
	InitFlickr()

####################################################################################################
# The plugin's main menu. 

def MainMenu():
		
	dir = MediaContainer()
	dir.art = R(PLUGIN_ARTWORK)
	
	#global username
	#global userid
	
	Log('XXXXXXX >>>>>> username is %s' % username)
	Log('XXXXXXX >>>>>> username type is %s' % type(username))
	Log('XXXXXXX >>>>>> userid is %s' % userid)
	Log('XXXXXXX >>>>>> userid type %s' % type(userid))
	
	if userid != None:
		#dir.Append(Function(DirectoryItem(GetPhotoStream, title="Photostream", thumb=R(PLUGIN_ICON_DEFAULT), summary="Photostream summary"), nsid=userid, nickname=username))
		#dir.Append(Function(DirectoryItem(GetPhotoStream, title=L("PHOTOSTREAM_TITLE") % username, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("PHOTOSTREAM_SUMMARY") % username), nsid=userid, nickname=username))
		dir.Append(Function(DirectoryItem(GetGroups, title=L("GROUPS_TITLE") % username, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("GROUPS_SUMMARY") % username), nsid=userid, nickname=username))
		dir.Append(Function(DirectoryItem(GetContacts, title=L("CONTACTS_TITLE") % username, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("CONTACTS_SUMMARY") % username), nsid=userid, nickname=username))
	
	dir.Append(Function(DirectoryItem(GetInterestingness, title=L("INTERESTINGNESS_TITLE"), thumb=R(PLUGIN_ICON_DEFAULT), summary=L("INTERESTINGNESS_SUMMARY"))))
	dir.Append(Function(DirectoryItem(GetTagHotlist, title=L("TAG_HOTLIST_TITLE"), thumb=R(PLUGIN_ICON_DEFAULT), summary=L("TAG_HOTLIST_SUMMARY"))))	
	
	dir.Append(PrefsItem(L("PREFERENCES_TITLE"), thumb=R(PLUGIN_ICON_PREFS), summary=L("PREFERENCES_SUMMARY")))
		 
	return dir

####################################################################################################
# Returns A users photostream

def GetPhotoStream(sender, nsid, nickname):
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	
	if nsid != None:
		dir = MediaContainer()
		dir.viewGroup = "PhotoStream"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's photostream" % nickname
	
		dir.Append(Function(DirectoryItem(GetRecent, title=L("RECENT_TITLE") % nickname, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("RECENT_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
		dir.Append(Function(DirectoryItem(GetFavorites, title=L("FAVORITES_TITLE") % nickname, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("FAVORITES_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
		dir.Append(Function(DirectoryItem(GetSets, title=L("SETS_TITLE") % nickname, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("SETS_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
		dir.Append(Function(DirectoryItem(GetTags, title=L("TAGS_TITLE") % nickname, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("TAGS_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
	
		return dir
	else:
		return ServiceDialog(sender, "GetPhotoStream", "No Photostream found for user '%s'" % nickname)
	
####################################################################################################
# Returns recent photos for the specified user

def GetRecent(sender, nsid, nickname, page=1):
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	if page != None:			Log("page=%s" % page)
	
	# Needs service flickr.people.getPublicPhotos	
	
	if nsid != None:
		dir = MediaContainer()
		dir.viewGroup = "Photos"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's recent photos" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		
		try:
			response = flickr.people_getPublicPhotos(user_id=nsid, page=page, per_page=PAGE_MAX_PHOTOS)
			
			if response.attrib["stat"] == "ok":
				Log("Photos Found") 
			
				photos = response.find("photos")
				
				if len(photos) > 0:
					for photo in photos:
						Log("Adding photo '%s'" % photo.attrib["id"])
						dir.Append(GetPhotoBasic(photo))
						
					if photos.attrib["page"] != photos.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetRecent, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), nsid=nsid, nickname=nickname, page=page+1))
					
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
						
		except FlickrError, message:
			Log("Flickr Error: %s" % message)	
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)

####################################################################################################
# Returns the Flickr community tag Hotlist by period
	
def GetTagHotlist(sender, period=None):
	
	dir = MediaContainer()
	dir.viewGroup = "Tags"
	dir.art = R(PLUGIN_ARTWORK)
	dir.title1 = PLUGIN_TITLE
	dir.title2 = "Tag Hotlist"
		
	if period != None:			
		Log("period=%s" % period)
		
		try:
			response = flickr.tags_getHotList(period=period, count=PAGE_MAX_PHOTOS)
			
			Log("Response Status: %s" % response.attrib['stat'])
			
			if response.attrib["stat"] == "ok":
				Log("Tags Found")	

				hottags = response.find("hottags")
				
				if len(hottags) > 0:
					for tag in hottags:
						title = tag.text
						summary = "View photos tagged with '%s'" % tag.text
											
						dir.Append(Function(DirectoryItem(GetPhotosByTag, title=title, thumb=R(PLUGIN_ICON_DEFAULT), summary=summary), tag=tag.text))
				else:
					Log("No Tags Found")
					return ServiceDialog(sender, L("MESSAGE_NO_TAGS_TITLE"), L("MESSAGE_NO_TAGS_SUMMARY") % nickname)

		except FlickrError, message:
			Log("Flickr Error: %s" % message)
	else:
		dir.Append(Function(DirectoryItem(GetTagHotlist, title="Today...", thumb=R(PLUGIN_ICON_DEFAULT), summary="View the most popular tags used today."), period="day"))
		dir.Append(Function(DirectoryItem(GetTagHotlist, title="This week...", thumb=R(PLUGIN_ICON_DEFAULT), summary="View the most popular tags used in the last week."), period="week"))
	
	return dir
	
####################################################################################################
# Returns a list of interesting photos from the Flickr community
	
def GetInterestingness(sender, page=1):
	if page != None:			Log("page=%s" % page)
	
	# Needs service flickr.interestingness.getList	
	
	dir = MediaContainer()
	dir.viewGroup = "Photos"
	dir.art = R(PLUGIN_ARTWORK)
	dir.title1 = PLUGIN_TITLE
	dir.title2 = L("INTERESTINGNESS_TITLE")
	
	thumb = R(PLUGIN_ICON_DEFAULT)
	
	try:
		extras = "license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media"
		response = flickr.interestingness_getList(page=page, per_page=PAGE_MAX_PHOTOS, extras=extras)
		
		if response.attrib["stat"] == "ok":
			Log("Photos Found")
			
			photos = response.find("photos") 

			if len(photos) > 0:
				for photo in photos:
					Log("Adding photo '%s'" % photo.attrib["id"])
					dir.Append(GetPhotoBasic(photo))
			
				if photos.attrib["page"] != photos.attrib["pages"]:
					dir.Append(Function(DirectoryItem(GetInterestingness, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), page=page+1))
					
				return dir
			else:
				return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
									
	except FlickrError, message:
		Log("Flickr Error: %s" % message)
		return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
	
####################################################################################################
# Returns a list of the specified users favorite photos

def GetFavorites(sender, nsid, nickname, page=1):	
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	if page != None:			Log("page=%s" % page)
	
	# Needs service flickr.favorites.getPublicList
	
	if nsid != None:
		dir = MediaContainer()
		dir.viewGroup = "Photos"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's Favorites" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)		
		
		try:
			extras = "license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media"		
			response = flickr.favorites_getPublicList(user_id=nsid, page=page, per_page=PAGE_MAX_PHOTOS, extras=extras)
			
			if response.attrib["stat"] == "ok":
				Log("Photos Found") 
			
				photos = response.find("photos")
				if len(photos) > 0:
					for photo in photos:
						Log("Adding photo '%s'" % photo.attrib["id"])
						dir.Append(GetPhotoBasic(photo))
					
					if photos.attrib["page"] != photos.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetFavorites, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), nsid=nsid, nickname=nickname, page=page+1))
							
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
					
		except FlickrError, message:
			Log("Flickr Error: %s" % message)	
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)
		
####################################################################################################
# Returns photo sets belonging to the specified user

def GetSets(sender, nsid, nickname):
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	
	# Needs service flickr.photosets.getList
	
	if nsid != None:
		dir = MediaContainer()
		dir.viewGroup = "Sets"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's Photo Sets" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		try:
			response = flickr.photosets_getList(user_id=nsid)
			
			if response.attrib["stat"] == "ok":
				Log("Sets Found")	
				
				photosets = response.find("photosets")
				if len(photosets) > 0:
					for photoset in photosets:
						Log("Adding photoset %s (%s)" % (photoset.attrib["id"], photoset.find("title").text))
	
						title = "%s (%s)" % (photoset.find("title").text, photoset.attrib["photos"])
						summary = photoset.find("description").text			
						photoset_id = photoset.attrib["id"]
						photoset_title = photoset.find("title").text
							
						dir.Append(Function(DirectoryItem(GetSetPhotos, title=title, thumb=thumb, summary=summary), photoset_id=photoset_id, photoset_title=photoset_title))
						
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_SETS_TITLE"), L("MESSAGE_NO_SETS_SUMMARY") % nickname)
			
		except FlickrError, message:
			Log("Flickr Error: %s" % message)
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)

####################################################################################################
# Returns all the photos in the specified set

def GetSetPhotos(sender, photoset_id, photoset_title, page=1):
	if photoset_id != None:			Log("photoset_id=%s" % photoset_id)
	if photoset_title != None:		Log("photoset_title=%s" % photoset_title)
	if page != None:				Log("page=%s" % page)
	
	# Needs flickr.photosets.getPhotos
	
	if photoset_id != None:
		dir = MediaContainer()
		dir.viewGroup = "Photos"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "Photo Set '%s'" % photoset_title
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		
		try:
			extras = "license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media"
			response = flickr.photosets_getPhotos(photoset_id=photoset_id, page=page, per_page=PAGE_MAX_PHOTOS, extras=extras)
			
			if response.attrib["stat"] == "ok":
				Log("Photos Found")
						
				photoset = response.find("photoset")
				
				if len(photoset) > 0:
					for photo in photoset:
						Log("Adding photo '%s'" % photo.attrib["id"])
						dir.Append(GetPhotoBasic(photo))
						
					if photoset.attrib["page"] != photoset.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetSetPhotos, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), photoset_id=photoset_id, photoset_title=photoset_title, page=page+1))	
						
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
					
		except FlickrError, message:
			Log("Flickr Error: %s" % message)	
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_SET_SPECIFIED_TITLE"), L("MESSAGE_NO_SET_SPECIFIED_SUMMARY"))

####################################################################################################
# Returns a list of the specified users contacts

def GetContacts(sender, nsid, nickname, page=1):
	if nsid != None:		Log("nsid=%s" % nsid)
	if nickname != None:	Log("nickname=%s" % nickname)
	if page != None:		Log("page=%s" % page)
	
	if nsid != None:	
		dir = MediaContainer()
		dir.viewGroup = "Contacts"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's Contacts" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)
				
		try:
			response = flickr.contacts_getPublicList(page=page, per_page=PAGE_MAX_PHOTOS, user_id=nsid)
			
			Log("Response Status: %s" % response.attrib['stat'])
			
			if response.attrib["stat"] == "ok":
				Log("Contacts Found")
				
				contacts = response.find("contacts")	

				if len(contacts) > 0:
					for contact in response.find("contacts"):
						Log("Adding Contact '%s' (%s)" % (contact.attrib["nsid"], contact.attrib["username"]))
						
						title = contact.attrib["username"]
						summary = "View %s's Photostream, sets, and groups." % contact.attrib["username"]
						dir.Append(Function(DirectoryItem(GetContact, title=title, thumb=None, summary=summary), nsid=contact.attrib["nsid"], nickname=contact.attrib["username"]))
					
					if contacts.attrib["page"] != contacts.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetContacts, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), nsid=nsid, nickname=nickname, page=page+1))
					
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_CONTACTS_TITLE"), L("MESSAGE_NO_CONTACTS_SUMMARY") % nickname)

		except FlickrError, message:
			Log("Flickr Error: %s" % message)
				
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)
	
####################################################################################################
# Returns a list of a contacts items

def GetContact(sender, nsid, nickname):

	dir = MediaContainer()
	dir.art = R(PLUGIN_ARTWORK)
	dir.art = R(PLUGIN_ARTWORK)
	dir.title1 = PLUGIN_TITLE
	dir.title2 = "Contact %s" % nickname
		
	dir.Append(Function(DirectoryItem(GetPhotoStream, title=L("PHOTOSTREAM_TITLE") % nickname, thumb=R(PLUGIN_ICON_DEFAULT), summary=L("PHOTOSTREAM_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
	dir.Append(Function(DirectoryItem(GetGroups, title=L("GROUPS_TITLE") % nickname, thumb=None, summary=L("GROUPS_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
	dir.Append(Function(DirectoryItem(GetContacts, title=L("CONTACTS_TITLE") % nickname, thumb=None, summary=L("CONTACTS_SUMMARY") % nickname), nsid=nsid, nickname=nickname))
		 
	return dir

####################################################################################################
# Returns groups belonging to the specified user

def GetGroups(sender, nsid, nickname):
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	
	# Needs service flickr.people.getPublicGroups
	
	if nsid != None:
		dir = MediaContainer()
		dir.viewGroup = "Sets"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's Groups" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		try:
			response = flickr.people_getPublicGroups(user_id=nsid)
			
			if response.attrib["stat"] == "ok":
				
				groups = response.find("groups")
				
				if len(groups) > 0:
					for group in response.find("groups"):
						group_id = group.attrib["nsid"]
						group_name = group.attrib["name"]
					
						Log("Adding group '%s' (%s)" % (group_id, group_name))
					
						title = group_name
						summary = "View photos from the group %s" % group_name
					
						dir.Append(Function(DirectoryItem(GetGroupPhotos, title=title, thumb=thumb, summary=summary), group_id=group_id, group_name=group_name))
					
					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_GROUPS_TITLE"), L("MESSAGE_NO_GROUPS_SUMMARY") % nickname)

		except FlickrError, message:
			Log("Flickr Error: %s" % message)
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)
	
####################################################################################################
# Returns all the photos for the specified group

def GetGroupPhotos(sender, group_id, group_name, page=1):
	if group_id != None:		Log("group_id=%s" % group_id)
	if group_name != None:		Log("group_name=%s" % group_name)
	if page != None:			Log("page=%s" % page)
	
	# Needs flickr.groups.pools.getPhotos
	
	if group_id != None:
		dir = MediaContainer()
		dir.viewGroup = "Photos"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "Group %s's photos" %  group_name
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		
		try:
			extras = "license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media"			
			response = flickr.groups_pools_getPhotos(group_id=group_id, page=page, per_page=PAGE_MAX_PHOTOS, extras=extras)
			
			if response.attrib["stat"] == "ok":
				Log("Photos Found")
						
				photos = response.find("photos")
				
				if len(photos) > 0:
					for photo in photos:
						Log("Adding photo '%s'" % photo.attrib["id"])
						dir.Append(GetPhotoBasic(photo))
					
					if photos.attrib["page"] != photos.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetGroupPhotos, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), group_id=group_id, group_name=group_name, page=page+1))

					return dir
				else:
					return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
					
		except FlickrError, message:
			Log("Flickr Error: %s" % message)	
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_GROUP_SPECIFIED_TITLE"), L("MESSAGE_NO_GROUP_SPECIFIED_SUMMARY"))
		
####################################################################################################
# Returns a PhotoItem with the most basic of data

def GetPhotoBasic(photo):
	title = photo.attrib["title"]
	image = GetPhotoURL(photo)
	thumb = GetThumbnailURL(photo)
	summary = None
	
	return PhotoItem(image, title=title, summary=summary, thumb=thumb)

####################################################################################################
# Returns a PhotoItem object for the specified photo_id

def GetPhoto(photo_id, secret):
	if photo_id != None:	Log("photo_id=%s" % photo_id)
	if secret != None:		Log("secret=%s" % secret)
	
	# Needs flickr.photos.getInfo (photo_id, secret)
	# Needs flickr.photos.getSizes (photo_id)
	
	if photo_id != None:		
		try:
			# Get the photo metadata
			
			response = flickr.photos_getInfo(photo_id=photo_id, secret=secret, extra="originalformat")
			
			if response.attrib["stat"] == "ok":
				Log("Got Photo Info")
				
						
				photo = response.find("photo")
				
				title = photo.find("title").text
				
				taglist = ""
				
				for tag in photo.find("tags"):
					taglist += "%s " % tag.text
				
				summary = ""
				if photo.find("description").text != None: summary += "%s\n" % photo.find("description").text
				if photo.find("owner").attrib["username"] != None: summary += "Taken by: %s\n" % photo.find("owner").attrib["username"]
				if photo.find("dates").attrib["taken"] != None: summary += "Taken on: %s\n" % photo.find("dates").attrib["taken"]
				if taglist != None: summary += "Tags: %s" % taglist
				
				image = GetPhotoURL(photo)
				thumb = GetThumbnailURL(photo)

			# Get the URL to the image and thumbnail 
			# This is lazy because I can build up the URL's to the images from the metadata attributes
					
			# response = flickr.photos_getSizes(photo_id=photo_id)
			
			# if response.attrib["stat"] == "ok":
			#	Log("Got Photo Sizes")
			#	
			#	for size in response.find("sizes"):
			#		label = size.attrib["label"]
			#		if label == "Large": image = size.attrib["source"]
			#		if label == "Thumbnail": thumb = size.attrib["source"]
				
			return PhotoItem(image, title=title, summary=summary, thumb=thumb)
			
		except FlickrError, message:
			Log("Flickr Error: %s" % message)	
		

####################################################################################################
# Returns the thumbnail image URL for a photograph

def GetThumbnailURL(photo):
	url = "http://farm%s.static.flickr.com/%s/%s_%s_m.jpg" % (
																photo.attrib["farm"], 
																photo.attrib["server"], 
																photo.attrib["id"], 
																photo.attrib["secret"]
															)
	Log("Thumbnail %s" % url)
	return url

####################################################################################################
# Returns the image URL for a photograph

def GetPhotoURL(photo):
	
	farm = photo.attrib["farm"]
	server = photo.attrib["server"]
	id = photo.attrib["id"]
	
	# is the secret information present ?
	
	if "originalsecret" in photo.attrib:		
		# Build the URL of the original image
		secret = "%s_o" % photo.attrib["originalsecret"]
		format = photo.attrib["originalformat"]
	else:
		
		# Build the URL of the next best thing
		secret = photo.attrib["secret"]
		format = "jpg"
				
	url = "http://farm%s.static.flickr.com/%s/%s_%s.%s" % (farm, server, id, secret, format)
	
	Log("Image %s" % url)
	return url

####################################################################################################
# Returns tags belonging to the specified user

def GetTags(sender, nsid, nickname):
	
	# Needs flickr.tags.getListUser (userid)
	
	if nsid != None:
		
		dir = MediaContainer()
		dir.viewGroup = "Tags"
		dir.art = R(PLUGIN_ARTWORK)
		dir.title1 = PLUGIN_TITLE
		dir.title2 = "%s's Tags" % nickname
		
		thumb = R(PLUGIN_ICON_DEFAULT)
		
		Log("Getting tags for %s (%s)" % (nickname, nsid))
		
		try:
			response = flickr.tags_getListUser(user_id=nsid)
			
			Log("Response Status: %s" % response.attrib['stat'])
			
			if response.attrib["stat"] == "ok":
				Log("Tags Found")	

				tags = response.find("who").find("tags")
				
				if len(tags) > 0:
					for tag in tags:
					
						#Log("Adding tag '%s'" % tag.text)
	
						title = tag.text
						
						if nsid != None:
							summary = "View %s's photos tagged with '%s'" % (nickname, tag.text)
						else:
							summary = "View photos tagged with '%s'" % tag.text
											
						dir.Append(Function(DirectoryItem(GetPhotosByTag, title=title, thumb=thumb, summary=summary), tag=tag.text, nsid=nsid, nickname=username))
			
				else:
					Log("No Tags Found")
					return ServiceDialog(sender, L("MESSAGE_NO_TAGS_TITLE"), L("MESSAGE_NO_TAGS_SUMMARY") % nickname)

		except FlickrError, message:
			Log("Flickr Error: %s" % message)
		
		return dir		
	else:
		return ServiceDialog(sender, L("MESSAGE_NO_USER_SPECIFIED_TITLE"), L("MESSAGE_NO_USER_SPECIFIED_SUMMARY") % nickname)

####################################################################################################
# Returns a list of photos by tag

def GetPhotosByTag(sender, tag, nsid=None, nickname=None, page=1):
	#if tag != None: 			Log("tag=%s" % tag)
	if nsid != None: 			Log("nsid=%s" % nsid)
	if nickname != None: 		Log("nickname=%s" % nickname)
	if page != None:			Log("page=%s" % page)
	
	# Needs flickr.photo.search (page, per_page, tags, user_id)
	
	dir = MediaContainer()
	dir.viewGroup = "Photos"
	dir.art = R(PLUGIN_ARTWORK)
	dir.title1 = PLUGIN_TITLE
	
	if nsid != None:
		dir.title2 = "Viewing %s's photos tagged with \'%s\'" % (nickname, tag)
	else:
		dir.title2 = "Viewing photos tagged with '%s'" % tag
		
	try:
		extras = "license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media"
		response = flickr.photos_search(page=page, per_page=PAGE_MAX_PHOTOS, tags=tag, user_id=nsid, media="photo", extras=extras)
			
		if response.attrib["stat"] == "ok":
			Log("Photos Found")	
			
			photos = response.find("photos")
			
			if len(photos) > 0:	
				for photo in photos:
					Log("Adding photo '%s'" % photo.attrib["id"])
					dir.Append(GetPhotoBasic(photo))
					
				if photos.attrib["page"] != photos.attrib["pages"]:
						dir.Append(Function(DirectoryItem(GetPhotosByTag, title="More", thumb=R(PLUGIN_ICON_MORE), summary="Get More"), tag=tag, nsid=nsid, nickname=nickname, page=page+1))

				return dir
			else:
				return ServiceDialog(sender, L("MESSAGE_NO_PHOTOS_TITLE"), L("MESSAGE_NO_PHOTOS_SUMMARY"))
		
	except FlickrError, message:
		Log("Flickr Error: %s"  % message)
		
####################################################################################################
# Returns a MessageContainer with a title and summary

def ServiceDialog(sender, title, summary):
	return MessageContainer(title, summary)

####################################################################################################
# Initialise the flickr client

def InitFlickr():	
	global flickr
	global userid
	global username

	Log("Creating Flickr Client")

	flickr = flickrapi.FlickrAPI(FLICKR_API_KEY, cache=True)
	flickr.cache = flickrapi.SimpleCache(timeout=300, max_entries=200)

	Log("Finding Flickr user '%s'" % Prefs.Get(PLUGIN_PREF_USERNAME))
	
	try:
		response = flickr.people_findByUsername(username=Prefs.Get(PLUGIN_PREF_USERNAME))
		Log("Response Status: %s" % response.attrib['stat'])
		
		if response.attrib["stat"] == "ok":
			Log("User found")	
			
			user = response.find("user")
		
			if user.find("username").text != None:
				userid = user.attrib["id"]
				username = user.find("username").text
			else:
				userid = None
				username = None

	except FlickrError, message:
		Log("Flickr Error: %s" % message)
		
		userid = None
		username = None
		
	Log("userid is %s" % userid)
	Log("username is %s" % username)

####################################################################################################
# Try and force encoding to utf-8

def Encode(value):	
	#Log(">> Asked to Encode value '%s'" % value)
	#Log(">> Value type is '%s'" % type(value))
	
	if value == None: 
		encoded == ""
	elif isinstance(value, str):
		encoded = value.encode('utf-8','ignore')
	elif isinstance(value, unicode):
		#return "ENCODE unicode"
		#return value.encode("latin-1")
		encoded = unicode(value).encode("utf-8")
	else:
		encoded = ">> !!! NONE Encoded %s Value" % type(value)
	
	Log(">> Encoded Value is '%s'" % encoded)
	
	return encoded
	
#	try:
#		value = value.encode('utf-8','ignore')
#	except UnicodeDecodeError:
#		value = "Encoing failed"		
#	return value