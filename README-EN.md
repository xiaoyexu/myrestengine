# My Rest Engine
The project is based on django framework, check [Django project](http://www.djangoproject.com) for details

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

* Use restEngine singleton instance instead of creating one

```
restEngine.registerProcessor('book', book)
f = open('<path to>api_metadata.yaml')
restEngine.loadMetadata(f)
```

* Set logger or response headers if needed, for example

```
# logger is django object like, i.e. logger = logging.getLogger('default')
restEngine.setLogger(logger)
restEngine.setResponseHeader({
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Accept, csrf-token',
    'Access-Control-Allow-Methods': 'GET,PUT,DELETE,POST,HEAD,OPTIONS',
    'Cache-Control': 'no-cache',
    'Access-Control-Expose-Headers': 'csrf-token'
})
```

* Add entry point in urls.py
```
url(r'^api/(?P<path>.*)$', views.api, name='api'),
```

and in views.py

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
  deletable: true
  creatable: true
  updatable: true
  key:
  - name: id
    type: int
  property:
  - name: firstName
    type: string
    updatable: true
  ...
```

* `deletable`,`creatable`,`updatable` with value `true` indicates whether the entity can be deleted created or updated, for entity makred as updatable, you need to mark on field level as well

* `expand` define the allowed navigation entity, allow navigate from user entity to roles and orgs entity set e.g.
```
user:
  ...
  expand:
  - name: roles
    type: roles
  - name: organization
    type: orgs
```
In this case, implement ``getListByKey`` method in roles or orgs processor, e.g.
```    
def getListByKey(self, keys, expandName=None):
        return Roles.objects.filter(user__id=keys['user']['id'])
```

name is used in ``expand`` and ``type`` refer to the name in ``sets`` in yaml file, the url looks like
```
user?_expand=roles
user?_expand=organization
```

## Database table

Recommend to have below 3 fields for all django models

1. createdAt
2. updatedAt
3. deleted

e.g.

```
createdAt = models.DateTimeField(auto_now_add=True, verbose_name=u"CreatedAt")
updatedAt = models.DateTimeField(auto_now=True, verbose_name=u"UpdatedAt")
deleted = models.BooleanField(default=False, verbose_name=u"Deleted")
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
def getListByKey(self, keys, expandName=None):
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

    You can also provide a model to json field mapping by overwrite method getPopulateFieldMapping, e.g.

    ```
    def getPopulateFieldMapping(self):
       return [
           'id',
           ('bookId', lambda m: m.book.id),
           ('bookName', lambda m: m.book.name),
           'category'
       ]
       ```

 2. Method post defines logic when request method is POST

    One way is to overwrite post(self, request) method, e.g.

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

      Another option is to overwrite getNewModel, e.g.

    ```
    def getNewModel(self):
        return BookComment()
    ```

    And overwrite postValidation for validation, e.g.

    ```
    def postValidation(self, json):
        bookId = json.get('bookId', None)
        userId = json.get('userId', None)
        text = json.get('text', None)
        if not bookId or not userId or not text:
            raise ParameterErrorException('No bookId userId or text given')

    ```

    And define fields mapping(from json field to model column, similar to getPopulateFieldMapping method). e.g.

    ```
    def __addParentId(m, v):
        m.parentComment = BookComment.objects.get(id=v)

    def getPopulateModelMapping(self):
        return [
            'text',
            ('parentId', self.__addParentId),
            ('replyToUser', self.__addReplyUserId),
            ('bookId', self.__setBookId),
            ('userId', self.__setUserId)
        ]
    ```

    __addParentId is a function take model, value as parameters and return a tuple. Or use lambda like
    ```
    ('parentId', lambda m, v: ('parentComment', BookComment.objects.get(id=v))),
    ```
    This function take parentId value, find related BookComment object as model filed name "parentComment".

 3. Method put defines logic when request method is PUT.

    In yaml file, mark entity as `updatable`, as well as fields that need to be updated

 4. Method delete defines logic when request method is DELETE, either overwrite `getDeleteModel(self, keys)` and `delete(self, request, keys)` method, e.g.

    In yaml file, mark entity as `deletable`

    If model has a column "deleted", then this flag will be set to True and saved, otherwise record will be deleted from database, by call model.delete()

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


Reserved url parameters are `_query`,`_fastquery`, `_order`, `_page`, `_pnum`, `_count`

Function | Example | Comment
---|---|---
\_query | entity?\_query=name="user" | Filter name equals "user".<br/> operator can be =, !=, @, !@, %, !%, >, >=, <, <= <br/> @ means ranges, e.g.  @"1,10" <br/> % means contains ignore case, e.g name%"xyz" (name contains "xyz")
\_fastquery | entity?\_fastquery="Jerry" | Customized text query 
\_order | entity?\_order=name,age | sort result by column, add -(minus) for descending sorting <br/> e.g. \_order=-id
\_page | entity?\_page=5 | Return record of page 5
\_pnum | entity?\_pnum=10 | Set 10 record for each page, default is 25
\_count | entity?\_count | Only return count number
\_distinct | entity?\_distinct=name,age | Return distinct column values by given column name, delimited by comma 

You may re-define the parameter name by `setParameterName`

```
restEngine = myrestengine.RESTEngine()
restEngine.setParameterName({
    "_query": "q",
    "_fastquery": "fq",
    "_expand": "exp",
    "_order": "o",
    "_page": "page",
    "_pnum": "size",
    "_distinct": "d",
    "_count": "c"
})
```

## _query syntax
In form of \<key\>=\"\<value\>\", value must be represented by single or double quotes 
```
name="abc"
name='abc'
age='20'
```

The filter string should be assigned to ``_query``

* , for and
```
users?_query=name="Jerry",age="18"
```

* | for or
```
users?_query=name="Jerry"|name="Mark"
```

* brackets for combination, without brackets, logic is built by order from left to right
```
users?_query=name="Jerry"|name="Mark",age="18"    等价于name="Jerry"|(name="Mark",age="18") 
users?_query=(name="Jerry"|name="Mark"),age="18"  
```

* Operators

Symbol | Sample | Coments 
---|---|---
% | name%"Jerry" | name contains Jerry without case sensitive <br> i.e django name__icontains
!% | name!%"Jerry" | name doesn't contain Jerry, without case sensitive
%% | name%"Jerry" | name contains Jerry with case sensitive <br> i.e django name__contains
!%% | name!%"Jerry" | name doesn't contain Jerry, with case sensitive
= | name="Jerry" | name equals to Jerry
!= | name!="Jerry" | name not equal to Jerry
< | age<"18" | age lower than 18 <br> i.e. django age__lt
<= | age<="18" | age lower equal than 18 <br> i.e. django age__lte
\> | age\>"18" | age greater than 18 <br> i.e. django age__gt
\>= | age>="18" | age greater equals than 18 <br> i.e. django age__gte
@ | age@"18,30" | range age gte 18 and lte 30 <br> i.e. django age__gte and age__lte

* Return result

Entity list return as arrary

```
[{
  "name": "Tom",
  "age": 18
},
{
  "name": "Jerry",
  "age": 18
}]
```

Single entity return as dictionary

```
{
  "name": "Tom",
  "age": 18
}
```

* Customize query format
Overwrite `customizedQueryParser`, in caes frontend framework generate url like
```
?page=1&size=3&filters[0][field]=name&filters[0][type]=like&filters[0][value]=x
```

Define format function as

```
def customizedQueryParser(self, request, params):
    i = 0
    q = []
    while request.GET.get('filters[%d][field]' % i, None) is not None:
        field = request.GET.get('filters[%d][field]' % i, None)
        type = request.GET.get('filters[%d][type]' % i, None)
        value = request.GET.get('filters[%d][value]' % i, None)
        q.append("""%s%%'%s'""" % (field, value))
        i += 1
    return ','.join(q)
```

* Customize return structure

Overwrite `customizedListResponse` 

```
def customizedListResponse(self, data, **kwargs):
    return {
        "data": data,
        "max_pages": kwargs['maxPages']
    }
```

In this case, result will be

```
{
  "data": [{
      "name": "Tom",
      "age": 18
    },
    {
      "name": "Jerry",
      "age": 18
    }],
  "max_pages": 1
}
```


