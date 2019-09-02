# 一个 RESTFUL 包装类
基于[Django项目](http://www.djangoproject.com) 的一个RESTFUL功能模块，是学习OData后的一个练习


## 在Django项目中使用

* 下载源文件，引入源文件包myrest（或为其他名字）

```
from .myrest import myparser, myrestengine
```

或使用 `pip install myrest`

```
from myrest import myrestengine
```


* 在app目录下定义的 api_metadata.yaml 文件如

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

在django的settings文件中设置变量，多个路径则只会加载第一个

```
MYREST_API_METADATA = ['<path to api_metadata.yaml>']
```



* 在需要的views.py中 实现一个处理器类，如Book处理器

```
class BookProcessor(RESTProcessor):
    def getBaseQuery(self):
        return Q(deleted=False)

    def getPopulateFieldMapping(self):
        return [
            'id',
            'name',
            'createdAt'
        ]
```

* 使用 `register` 加注，如

```
@myrestengine.register('book', Book)
class BookProcessor(RESTProcessor):
   ...
```

* 默认引擎为myrestengine.ENGINE，可设置log对象和返回response的通用header，如

```
# logger is django object like, i.e. logger = logging.getLogger('default')
myrestengine.ENGINE.setLogger(logger)
myrestengine.ENGINE.setResponseHeader({
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Accept, csrf-token',
    'Access-Control-Allow-Methods': 'GET,PUT,DELETE,POST,HEAD,OPTIONS',
    'Cache-Control': 'no-cache',
    'Access-Control-Expose-Headers': 'csrf-token'
})
```

* 增加一个处理所有restful api的入口，如urls.py中

```
url(r'^api/(?P<path>.*)$', views.api, name='api'),
```

和views.py中
```
@csrf_exempt
@myrestengine.requireProcess()
def api(request, path):
    return myrestengine.ENGINE.handle(request, path)
```


## 元数据（Metadata）
* 实体（Entity） - 代表一行数据，通常对应数据表的一行
* 实体集合（Entities） - 行数据的集合

新实体增加后，需要修改api_metadata.yaml文件，重启django服务（暂无动态加载）

api_metadata.yaml文件包括
* `sets`, 实体集合和单体名字，如
```
users: user
```

* `实体单体` 将定义其中的字段、成员，如下user包含主键(key)为name，类型为int，字段有firstname，类型string
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

* 含有 `deletable`,`creatable`,`updatable` 为 `true` 的实体分别可执行删除、创建、修改操作，标记实体为`updatable`时，还需标注字段级别是否可修改

* `expand` 定义该实体可扩展到的其他实体, 即相关记录，如下表示user可有对应相关的roles（角色）和orgs（组织）
```
user:
  ...
  expand:
  - name: roles
    type: roles
  - name: organization
    type: orgs
```

这种情况下，在roles和orgs处理类中实现 ``getListByKey`` 方法，如
```    
def getListByKey(self, keys, expandName=None):
        return Roles.objects.filter(user__id=keys['user']['id'])
```

其中name定义 ``expand`` 的名字，而 ``type`` 是 yaml 文件中 sets 中的名字，url 形如
```
user?_expand=roles
user?_expand=organization
```

## 数据库表

建议所有Django数据库包括如下字段

1. createdAt
2. updatedAt
3. deleted

即

```
createdAt = models.DateTimeField(auto_now_add=True, verbose_name=u"CreatedAt")
updatedAt = models.DateTimeField(auto_now=True, verbose_name=u"UpdatedAt")
deleted = models.BooleanField(default=False, verbose_name=u"Deleted")
```

## 处理器（Processor）
对某实体（表）的所有CRUD操作，通过继承RESTProcessor类实现

* 创建一个User的处理器
```
class UserProcessor(RESTProcessor):
    pass
```

* 将处理器注册到引擎上，如下user为起的实体名，BP为django models.py中的一个model（表）

```
userProcessor = UserProcessor(BP)
...
restEngine.registerProcessor('user', userProcessor)
```



* 实现对应的方法，如getList, getSingle, post, put, head, delete, convertData

大多数情况下你不需要覆盖 getList, getSingle 方法, 对于GET方法，你可能需要覆盖如下几个

 1. getBaseQuery 定义了获取实体集合或单个实体记录的基本过滤条件, 如

```
def getBaseQuery(self):
        return Q(valid=True)
```

 2. getFastQuery 定义了如果url上提供了 \_fastquery 参数的情况下的搜索条件，如下表示当有?\_fastquery=xiaoye 时该如何过滤数据
 ```
def getFastQuery(self, text):
        return Q(Q(firstName__icontains=text) | Q(lastName__icontains=text))
 ```

 3. getListByKey 定义了扩展实体的返回逻辑，比如当url为 api/orgs(1)/users时，返回的user列表应该基于org id的结果过滤
```
def getListByKey(self, keys, expandName=None):
        orgId = keys['org']['id']
        userIds = [bpr.bpB.id for bpr in BPRelation.objects.filter(relation__key='HAS_MEMBER', bpA__id=orgId)]
        return self.getBaseDjangoModel().objects.filter(id__in=userIds)
```

* 其他方法

 1. convertData 方法实现model到json格式的转换, 甚至可以有language参数，如

    ```
    def convertData(self, model, language=None):
        record = {}
        record['id'] = model.id
        ...
        return record
    ```

    也可以提供一个数组，用来将model对应到json，如

    ```
    def getPopulateFieldMapping(self):
       return [
           'id',
           ('bookId', lambda m: m.book.id),
           ('bookName', lambda m: m.book.name),
           'category'
       ]
    ```

 2. 创建记录操作

    一种是覆盖 post(self, request) 方法，如

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

      或者覆盖 getNewModel 方法，如

    ```
    def getNewModel(self):
        return BookComment()
    ```

    并覆盖 postValidation 实现验证，如

    ```
    def postValidation(self, json):
        bookId = json.get('bookId', None)
        userId = json.get('userId', None)
        text = json.get('text', None)
        if not bookId or not userId or not text:
            raise ParameterErrorException('No bookId userId or text given')

    ```

    实现从json到model的转换逻辑，类似 getPopulateFieldMapping method 如

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

    __addParentId 为一个有model和value为参数的函数，用来设置model，或者用lambda表达式
    ```
    ('parentId', lambda m, v: ('parentComment', BookComment.objects.get(id=v))),
    ```
    上面这个函数接受json中parentId的值，作为id，找到BookComment model，设置到对应实体中，名为parentComment

 3. 修改记录操作

    在yaml文件中标记实体为 `updatable`， 然后将需要更新的字段也同样标记上

 4. 删除实体操作
 
    在yaml文件中标记实体为 `deletable` 即可

    如果model上有一个deleted，那么会将其设置为True，否则使用model.delete()删除

## API 参考

对应实体，如果只有一个key字段，则使用形如 entity(&lt;keyvalue&gt;) 来访问一个实体

如果是数字型，则直接使用，如果是字符串，则需要加单引号(')或双引号(")，如

```
/api/user(123)
/api/role("rolename")
/api/role('rolename')
```

多个字段作为key，则形如 entity(&lt;keyname&gt;=&lt;keyvalue&gt;)，如

```
/api/entity(name="XYZ",age=18)
/api/entity(name="XYZ",age=18, grade=5)
```

或者不提供字段名，则每个字段按metadata文件中定义的顺序

```
/api/entity("XYZ",18)
/api/entity("XYZ",18,5)
```


保留的url上的参数名 `_query`, `_fastquery`, `_order`, `_page`, `_pnum`, `_count`, `_distinct`

参数 | 例子 | 含义
---|---|---
\_query | entity?\_query=name="user" | 取所有name为"user"的记录<br/> 操作符有 =, !=, @, !@, %, !%, >, >=, <, <= <br/> @ 表示范围如 @"1,10" <br/> % 表示忽略大小写的包含，如 name%"xyz" (name 包含字符串 "xyz")
\_fastquery | entity?\_fastquery="Jerry" | 使用自定义的多字段搜索
\_order | entity?\_order=name,age | 排序字段，-(减号) 表示降序<br/> 如 \_order=-id
\_page | entity?\_page=5 | 返回第5页数据
\_pnum | entity?\_pnum=10 | 设置每页大小，默认为25
\_count | entity?\_count | 只返回记录数
\_distinct | entity?\_distinct=name,age | 返回指定列的distinct记录，多列用逗号分隔


可重定义参数名，使用 `setParameterName`

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

## _query语法规则
\<key\>=\"\<value\>\"形式，value 必须用单引号或双引号表示，如
```
name="abc"
name='abc'
age='20'
```

整个过滤表达式放在 ``_query`` 中

* 逗号(,)分隔表示 and，如
```
users?_query=name="Jerry",age="18"
```

* 竖线(|)分隔表示 or，如
```
users?_query=name="Jerry"|name="Mark"
```

* 括号用来保证运算优先级，否则以先序构造
```
users?_query=name="Jerry"|name="Mark",age="18"    等价于name="Jerry"|(name="Mark",age="18") 
users?_query=(name="Jerry"|name="Mark"),age="18"  
```

* 操作符

符号 | 例子 | 含义 
---|---|---
% | name%"Jerry" | name 包含字符串 Jerry，不区分大小写 <br> 对应django name__icontains
!% | name!%"Jerry" | name 不包含字符串 Jerry，不区分大小写
%% | name%%"Jerry" | name 包含字符串 Jerry，区分大小写 <br> 对应django name__contains
!%% | name!%%"Jerry" | name 不包含字符串 Jerry，区分大小写
= | name="Jerry" | name 等于 Jerry
!= | name!="Jerry" | name 不等于 Jerry
< | age<"18" | age 小于 18 <br> 对应django age__lt
<= | age<="18" | age 小于等于 18 <br> 对应django age__lte
\> | age\>"18" | age 大于 18 <br> 对应django age__gt
\>= | age>="18" | age 小于等于 18 <br> 对应django age__gte
@ | age@"18,30" | 范围 age 大于等于18小于等于30 <br> 对应django age__gte 和 age__lte

* 返回结果

实体集合，默认返回为数组，如

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

单个实体，默认返回为字典，如

```
{
  "name": "Tom",
  "age": 18
}
```

* 自定义query转换
如需转换query格式，可覆盖 `customizedQueryParser`，如前端框架可能产生url
```
?page=1&size=3&filters[0][field]=name&filters[0][type]=like&filters[0][value]=x
```

可自定义转换，如

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

* 自定义返回结构

如需变更集合返回结构，可覆盖 `customizedListResponse` 方法，如

```
def customizedListResponse(self, data, **kwargs):
    return {
        "data": data,
        "max_pages": kwargs['maxPages']
    }
```

这样，返回结果如


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



