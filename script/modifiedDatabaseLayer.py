#!/usr/bin/env python3.3
# -*- coding: utf-8 -*-
#
# Database layer
#  translates database calls to functions
#
# Software is free software released under the "Modified BSD license"
#

# Copyright (c) 2014-2016       Pieter-Jan Moreels - pieterjan.moreels@gmail.com

# imports
import ast
import sqlite3
import pymongo
import re

from lib.Config import Configuration as conf
from lib.ProgressBar import progressbar

# Variables
db=conf.getMongoConnection()
colCVE=         db['cves']
colCPE=         db['cpe']
colCWE=         db['cwe']
colCPEOTHER=    db['cpeother']
colWHITELIST=   db['mgmt_whitelist']
colBLACKLIST=   db['mgmt_blacklist']
colUSERS=       db['mgmt_users']
colINFO=        db['info']
colVFEED=       db['vfeed']
colRANKING=     db['ranking']
colMSBULLETIN=  db['ms']
colCAPEC=       db['capec']
colPlugSettings=db['plugin_settings']

# Functions
def sanitize(x):
  if type(x)==pymongo.cursor.Cursor:
    x=list(x)
  if type(x)==list:
    for y in x: sanitize(y)
  if x and  "_id" in x: x.pop("_id")
  return x

# DB Functions
def ensureIndex(col, field):
  db[col].ensure_index(field)

def drop(col):
  db[col].drop()

def setColUpdate(collection, date):
  colINFO.update({"db": collection}, {"$set": {"last-modified": date}}, upsert=True)

def insertCVE(cve):
  colCVE.insert(cve)

def updateCVE(cve):
  colCVE.update({"id": cve['id']}, {"$set": {"cvss": cve['cvss'], "summary": cve['summary'], "references": cve['references'],
                                             "cwe": cve['cwe'], "vulnerable_configuration": cve['vulnerable_configuration'],
                                             "vulnerable_configuration_cpe_2_2": cve['vulnerable_configuration_cpe_2_2'], 'last-modified': cve['Modified']}})

def updateMSBulletin(ms):
  colMSBULLETIN.update({"id": ms['id']},{"$set": ms}, upsert=True)

def bulkUpdate(collection, data):
  if len(data)>0:
    bulk=db[collection].initialize_ordered_bulk_op()
    for x in data:
      bulk.find({'id': x['id']}).upsert().update({'$set': x})
    bulk.execute()

def bulkvFeedUpdate(dbpath, vfeedmap):
  # connect to sqlite db
  con = sqlite3.connect(dbpath+'/vfeed.db')
  con.text_factory = lambda x: x.decode("utf-8", "ignore")
  c = con.cursor()
  # loop over sqlite db and insert into vfeed collection
  for vmap in progressbar(vfeedmap):
    e = c.execute('SELECT * FROM %s' % vmap)
    names = list(map(lambda x: x[0], e.description))
    bulk = colVFEED.initialize_ordered_bulk_op()
    for r in e:
      try:
        if vmap == 'map_redhat_bugzilla':
          icveid = names.index('redhatid')
        else:
          icveid = names.index("cveid")
      except Exception as ex:
        sys.exit('Exeption in %s: %s' % (vmap, ex))
        continue
      mapArray={}
      for i in range(0,len(r)):
        if not (names[i] == "cveid"):
          mapArray[str(names[i])]=str(r[i])
      if not vmap=='map_redhat_bugzilla':
        bulk.find({'id': r[icveid]}).upsert().update({"$set":{vmap:mapArray}})
      else:
        bulk.find({'map_cve_redhat.redhatid': r[icveid]}).update({"$set":{vmap:mapArray}})
    bulk.execute()

def cpeotherBulkInsert(cpeotherlist):
  colCPEOTHER.insert(cpeotherlist)

def dropCollection(col):
  return db[col].drop()

def getTableNames():
  return db.collection_names()

# API Functions
def cvesForCPE(cpe):
  if not cpe: return []
  return sanitize(colCVE.find({"vulnerable_configuration": {"$regex": cpe}}).sort("Modified", -1))

# User Functions
def addUser(user, pwd, admin=False):
  if admin:
    colUSERS.insert({'username':user, 'password':pwd, 'master': True})
  else:
    colUSERS.insert({'username':user, 'password':pwd})

def changePassword(user, pwd):
  colUSERS.update({'username': user}, {'$set': {'password': pwd}})

def deleteUser(user):
  colUSERS.remove({'username': user})

def setAdmin(user, admin):
  if admin:
    colUSERS.update({'username': user}, {'$set': {'master': True}})
  else:
    colUSERS.update({'username': user}, {'$unset': {'master': ""}})

def isMasterAccount(user):
  return False if colUSERS.find({"username": user, "master": True}).count() == 0 else True

def userExists(user):
  return True if colUSERS.find({"username": user}).count() > 0 else False

def isSingleMaster(user):
  return True if len(list(colUSERS.find({"username": {"$ne": user}, "master": True}))) == 0 else False

# Query Functions
# Generic data
def getCVEs(limit=False, query=[], skip=0, cves=None, collection=None):
  col=colCVE if not collection else db[collection]
  if type(query) == dict: query=[query]
  if type(cves) == list: query.append({"id": {"$in": cves}})
  if len(query) == 0:
    cve=col.find().sort("Modified", -1).limit(limit).skip(skip)
  elif len(query)  == 1:
    cve=col.find(query[0]).sort("Modified", -1).limit(limit).skip(skip)
  else:
    cve=col.find({"$and": query}).sort("Modified", -1).limit(limit).skip(skip)
  return sanitize(cve)


def getCVEsNewerThan(dt, cpe):
  return sanitize(getCVEs(query={'last-modified': {'$gt': dt}}))

################################################################################################################################################################################################################################################################################################
# axel query
# Generic data
def getCve(limit=False, query=[], skip=0, cves=None, collection=None):
  col=colCVE if not collection else db[collection]
  if type(query) == dict: query=[query]
  if type(cves) == list: query.append({"id": {"$in": cves}})
  if len(query) == 0:
    cve=col.find().sort("cvss", -1).limit(limit).skip(skip)
  elif len(query)  == 1:
    cve=col.find(query[0]).sort("cvss", -1).limit(limit).skip(skip)
  else:
    cve=col.find({"$and": query}).sort("cvss", -1).limit(limit).skip(skip)
  return sanitize(cve)

# get me items where cpe is mentioned and they are more updated than given date and they have superior security level than given value
def getCveNewerThan(dt, cpe, lvl):
  return sanitize(getCve(query={'last-modified': {'$gt': dt} , "vulnerable_configuration": {"$regex": cpe} , "cvss": {'$gt':lvl}}))

################################################################################################################################################################################################################################################################################################

def getCVEIDs(limit=-1):
  return [x["id"] for x in colCVE.find().limit(limit).sort("Modified", -1)]

def getCVE(id, collection=None):
  col=colCVE if not collection else db[collection]
  return sanitize(col.find_one({"id": id}))

def getCPE(id):
  return sanitize(colCPE.find_one({"id": id}))

def getCPEs():
  return sanitize(colCPE.find())
  
def getAlternativeCPE(id):
  return sanitize(colCPEOTHER.find_one({"id": id}))

def getAlternativeCPEs():
  return sanitize(colCPEOTHER.find())
  
def getvFeed(id):
  return sanitize(colVFEED.find_one({'id': id}))

def getCPEMatching(regex, fullSearch=False):
  lst=list(colCPE.find({"id": {"$regex": regex}}))
  if fullSearch: lst.extend(colCPEOTHER.find({"id": {"$regex": regex}}))
  return lst

def getFreeText(text):
  try: # Before Mongo 3
    return [x["obj"] for x in db.command("text", "cves", search=text)["results"]]
  except: # As of Mongo 3
    return sanitize(colCVE.find({"$text":{"$search":text}}))

def getSearchResults(search):
  result={'data':[]}
  regSearch = re.compile(re.escape(search), re.I)
  vFeedLinks=['map_cve_ms.msid', 'map_cve_redhat.redhatid',
              'map_redhat_bugzilla.redhatid', 'map_cve_ubuntu.ubuntuid',
              'map_cve_suse.suseid', 'map_cve_fedora.fedoraid', 'map_cve_hp.hpid',
              'map_cve_cisco.ciscoid']
  links =  {'n': 'Link',     'd': []}
  for vLink in vFeedLinks:
    links['d'].extend(sanitize(colVFEED.find({vLink: {'$in': [regSearch]}})))
  
  try:
    textsearch={'n': 'Text search', 'd': getFreeText(search)}
  except:
    textsearch={'n': 'Text search', 'd': []}
    result['errors']=['textsearch']

  for collection in [links, textsearch]:
    for item in collection['d']:
      # Check if already in result data
      if not any(item['id']==entry['id'] for entry in result['data']):
        entry=getCVE(item['id'])
        entry['reason']=collection['n']
        result['data'].append(entry)
  return result

def getCAPECFor(cwe):
  return sanitize(colCAPEC.find({'related_weakness': {'$in': [cwe]}}))

def getCAPEC(cweid):
  return sanitize(colCAPEC.find_one({'id': cweid}))

def getCWEs():
  return sanitize(sorted(colCWE.find(), key=lambda k: int(k['id'])) )

def getInfo(collection):
  return sanitize(colINFO.find_one({"db": collection}))

def getLastModified(collection):
  info=getInfo(collection)
  return info['last-modified'] if info else None

def getSize(collection):
  return db[collection].count()

def vFeedLinked(key, val):
  cveList=[x['id'] for x in colVFEED.find({key: val})]
  return sanitize(getCVEs(query={'id':{'$in':cveList}}))

def getDBStats():
  cols=['cve', 'cpe', 'cpeOther', 'capec', 'd2sec', 'vendor', 'vfeed']
  stats={x+'A': getSize(x.lower()) for x in cols}
  stats['cveA']=getSize('cves')
  stats.update({x+'U': getLastModified(x.lower()) for x in cols})
  stats.update({'blA': colBLACKLIST.count(), 'wlA':colWHITELIST.count()})
  stats.update({'dbOnDisk': db.command("dbstats")['storageSize'], 'dbSize':db.command('dbstats')['dataSize']})
  stats['dbName']=conf.getMongoDB()
  return stats

# Dynamic data
def getWhitelist():
  return sanitize(colWHITELIST.find())

def isInWhitelist(cpe):
  return True if colWHITELIST.find({'id': cpe}).count()>0 else False

def addToWhitelist(cpe, type, comments=None):
  if comments:
    colWHITELIST.insert({'id': cpe, 'type': type, 'comments': comments})
  else:
    colWHITELIST.insert({'id': cpe, 'type': type})

def removeFromWhitelist(cpe):
  colWHITELIST.remove({'id': cpe})

def updateWhitelist(oldCPE, newCPE, type, comments=None):
  if comments:
    colWHITELIST.update({'id': oldCPE}, {'id': newCPE, 'type': type, 'comments': comments})
  else:
    colWHITELIST.update({'id': oldCPE}, {'id': newCPE, 'type': type})

def getBlacklist():
  return sanitize(colBLACKLIST.find())

def isInBlacklist(cpe):
  return True if colBLACKLIST.find({'id': cpe}).count()>0 else False

def addToBlacklist(cpe, type, comments=None):
  if comments:
    colBLACKLIST.insert({'id': cpe, 'type': type, 'comments': comments})
  else:
    colBLACKLIST.insert({'id': cpe, 'type': type})

def removeFromBlacklist(cpe):
  colBLACKLIST.remove({'id': cpe})

def updateBlacklist(oldCPE, newCPE, type, comments=None):
  if comments:
    colBLACKLIST.update({'id': oldCPE}, {'id': newCPE, 'type': type, 'comments': comments})
  else:
    colBLACKLIST.update({'id': oldCPE}, {'id': newCPE, 'type': type})

def getRules(list):
  if list.lower()=='whitelist':
    col=colWHITELIST
  elif list.lower()=='blacklist':
    col=colBLACKLIST
  else:
    return []
  rlist=col.find({'type':'cpe'}).distinct('id')
  rlist.extend(["cpe:2.3:([^:]*:){9}"+re.escape(x) for x in col.find({'type':'targethardware'}).distinct('id')])
  rlist.extend(["cpe:2.3:([^:]*:){8}"+re.escape(x) for x in col.find({'type':'targetsoftware'}).distinct('id')])
  return rlist

def addRanking(cpe, key, rank):
  item = findRanking(cpe)
  if item is None:
    colRANKING.update({'cpe': cpe}, {"$push": {'rank': {key: rank}}}, upsert=True)
  else:
    l = []
    for i in item['rank']:
      i[key] = rank
      l.append(i)
    colRANKING.update({'cpe': cpe}, {"$set": {'rank': l}})
  return True

def removeRanking(cpe):
  return sanitize(colRANKING.remove({'cpe': {'$regex': cpe}}))

def findRanking(cpe=None, regex=False):
  if not cpe:
    return sanitize(colRANKING.find())
  if regex:
    return sanitize(colRANKING.find_one({'cpe': {'$regex': cpe}}))
  else:
    return sanitize(colRANKING.find_one({'cpe': cpe}))
    
# Users
def getUsers():
  return sanitize(colUSERS.find())

def getUser(user):
  return sanitize(colUSERS.find_one({"username": user}))

###########
# Plugins #
###########
# Settings
def p_writeSetting(plugin, setting, value):
  colPlugSettings.update({"plugin": plugin}, {"$set": {setting: value}}, upsert=True)

def p_readSetting(plugin, setting):
  data = colPlugSettings.distinct(setting, {'plugin': plugin})
  if len(data) !=0: return data[0]
  else:             return None

# Query
def p_queryData(collection, query):
  return sanitize(db['plug_%s'%collection].find(query))

def p_queryOne(collection, query):
  return sanitize(db['plug_%s'%collection].find_one(query))

# Data manipulation
def p_addEntry(collection, data):
  db['plug_%s'%collection].insert(data)

def p_removeEntry(collection, query):
  db['plug_%s'%collection].remove(query)

def p_bulkUpdate(collection, keyword, data):
  if len(data)>0:
    bulk=db['plug_%s'%collection].initialize_ordered_bulk_op()
    for x in data:
      bulk.find({keyword: x[keyword]}).upsert().update({'$set': x})
    bulk.execute()

def p_addToList(collection, query, listname, data):
  if type(data) != list: data=[data]
  current = list(p_queryData(collection, query))
  if len(current)==0:
    p_addEntry(collection, query)
  for entry in current:
    if listname in entry:
      data=list(set([repr(x) for x in data])-set([repr(x) for x in entry[listname]]))
      data=[ast.literal_eval(x) for x in data]
    if data:
      db['plug_%s'%collection].update(query, {"$addToSet": {listname: {"$each": data}}})

def p_removeFromList(collection, query, listname, data):
  if   type(data) == dict: 
    db['plug_%s'%collection].update(query, {"$pull": {listname: data}})
  elif type(data) != list: data=[data]
  db['plug_%s'%collection].update(query, {"$pullAll": {listname: data}})
