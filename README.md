# My Rest Engine
The project is based on django framework, check [Django project](http://www.djangoproject.com) for details

***Development still in progress***

## Metadata
When new entity added, update api_metadata.yaml file, especially the navigation changes.

The file contains
* `sets`, define the entity set name and it's entity, e.g.
```
users: user
```

* `<entity name>` define entity and it's property, e.g
```
user:
  key:
  - name: id
  - type: int
  property:
  - name: firstName
  - type: string
  ...
```

* `expand` define the allowed navigation entity, allow navigate from user entity to roles and orgs entity set e.g.
```
user:
  ...
  expand:
  - roles
  - orgs
```
In this case, implement ``getListByKey`` method in roles or orgs processor, e.g.
```    
def getListByKey(self, keys):
        return Roles.objects.filter(user__id=keys['user']['id'])
```

## Processor
The CRUD function of entity is handled by a processor which extends from RESTProcessor object. To simple create a processor, follow:
* Create subclass of RESTProcessor, e.g.

```
class UserProcessor(RESTProcessor):
    pass
```

* Register processor to a entity name, e.g.

```
userProcessor = UserProcessor(BP)
...
restEngine.registerProcessor('user', userProcessor)
```
Notice BP is the django model object defined in models.py


* Overwrite necessory methods(getList, getSingle, post, put, head, delete, convertData)

 *In most cases you don't need to overwrite getList, getSingle methods, below are the functions you can overwrite for GET method.*
 1. getBaseQuery defines basic query condition for get list or single record, e.g.
```
def getBaseQuery(self):
        return Q(valid=True)
```

 2. getFastQuery defines query condition if parameter \_fastquery is used, this is for fuzzy search, e.g. search given text in firstName and lastName column:
 ```
def getFastQuery(self):
        return Q(Q(firstName__icontains=text) | Q(lastName__icontains=text))
 ```

 3. getListByKey return query set if navigated from other entity, e.g. when calling api/orgs(1)/users, the user list is filtered by org id
```
def getListByKey(self, keys):
        orgId = keys['org']['id']
        userIds = [bpr.bpB.id for bpr in BPRelation.objects.filter(relation__key='HAS_MEMBER', bpA__id=orgId)]
        return self.getBaseDjangoModel().objects.filter(id__in=userIds)
```

* Other methods for post, put, delete

 1. convertData returns json result of a django model object, phrase text can be retrieved if language is given. E.g.
```
def convertData(self, model, language=None):
        record = {}
        record['id'] = model.id
        ...
        return record
```

 2. Method post defines logic when request method is POST, e.g.
```
def post(self, request):
        jsonBody = request.jsonBody
        # Get fields from jsonBody and create data
        firstName = jsonBody.get('firstName', None)
        user = User()
        user.firstName = firstName
        user.save()
        return self.convertData(user)
 ```

 3. Method put defines logic when request method is PUT
```
def put(self, request, keys):
        key = keys['user'][id]
        jsonBody = request.jsonBody
        firstName = jsonBody.get('firstName', None)
        # update user
        user = User.objects.get(id=key)
        user.firstName = firstName
        user.save()
        return {}
```

 4. Method delete defines logic when request method is DELETE
```
def delete(request, keys):
        key = keys['user']['id']
        user = User.objects.get(id=key)
        user.valid = False
        user.save()
        return {}
```

## API Reference

For each entity, if only one key field is available use pattern entity(&lt;keyvalue&gt;) to access single object.

if value type is int, use number directly, if value type is string, it must contains quotes (') or double quotes ("), e.g.

```
/api/user(123)
/api/role("rolename") or /api/role('rolename')
```

For multiple key field, use pattern entity(&lt;keyname&gt;=&lt;keyvalue&gt;), e.g.

```
/api/entity(name="XYZ",age=18)
/api/entity(name="XYZ",age=18, grade=5)
```

Or pure values without keyname, key order in metadata file will be used to map each field.

```
/api/entity("XYZ",18)
/api/entity("XYZ",18,5)
```


Reserved url parameters are `_query`, `_order`, `_skip`, `_top`, `_count`

Function | Example | Comment
---|---|---
\_query | entity?\_query=name="user" | Filter name equals "user".<br/> operator can be =, !=, @, !@, %, !%, >, >=, <, <= <br/> @ means ranges, e.g.  @"1,10" <br/> % means contains ignore case, e.g name%"xyz" (name contains "xyz")
\_order | entity?\_order=name,age | sort result by column, add -(minus) for descending sorting <br/> e.g. \_order=-id
\_page | entity?\_page=5 | Return record of page 5
\_pnum | entity?\_pnum=10 | Set 10 record for each page, default is 25
\_count | entity?\_count | Only return count number

## Usage in django project

In the view where you want to define an api entry
* Define processor class for a entity

```
class BookProcessor(RESTProcessor):
    def getBaseQuery(self):
        return Q()

    def getPopulateFieldMapping(self):
        return [
            'id',
            'name',
            'createdAt'
        ]
```

* Create processor instance, Book is the django model class defined in your models.py

```
book = BookProcessor(Book)
```

* Create rest Engine

```
restEngine = RESTEngine()
restEngine.registerProcessor('book', book)
f = open('<path to>api_metadata.yaml')
restEngine.loadMetadata(f)
```

* Add entry point

```
@csrf_exempt
@requireProcess(need_login=False)
def api(request, path):
    return restEngine.handle(request, path)
```

Demo api_metadata.yaml file

```
sets:
  books: book
book:
  key:
  - name: id
    type: int
  property:
  - name: name
    type: string
  - name: createdAt
    type: string
```

Demo view file

```
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import *
from .myrestengine import *
import logging

log = logging.getLogger('default')
log.info('logger initialized')


class BookProcessor(RESTProcessor):
    def getBaseQuery(self):
        return Q()

    def getPopulateFieldMapping(self):
        return [
            'id',
            'name',
            'createdAt'
        ]


book = BookProcessor(Book)

restEngine = RESTEngine()
restEngine.registerProcessor('book', book)
try:
    f = open('./book/api_metadata.yaml')
    restEngine.loadMetadata(f)
except Exception as e:
    f = open('../book/api_metadata.yaml')
    restEngine.loadMetadata(f)


@csrf_exempt
@requireProcess(need_login=False)
def api(request, path):
    return restEngine.handle(request, path)

```
