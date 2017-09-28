# -*- coding: UTF-8 -*-
from django.http import HttpResponse
from .myparser import *
from xml.etree.ElementTree import Element, tostring, fromstring
from django.utils import timezone
from django.db.models import Q
from django.db.models.query import QuerySet
from django.core.exceptions import *
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import random, re, pickle, yaml, base64, json, time, datetime


class UserContext(object):
    def __init__(self):
        self.csrfTokenInfo = ''
        self.languageKey = ''


class MetadataException(Exception):
    pass


class BadRequestException(Exception):
    pass


class NotImplementedException(Exception):
    pass


class NoAuthException(Exception):
    pass


class InternalException(Exception):
    pass


class ParameterErrorException(BadRequestException):
    pass


class CreateErrorException(BadRequestException):
    pass


class UpdateErrorException(BadRequestException):
    pass


class DeleteErrorException(BadRequestException):
    pass


class ReadErrorException(BadRequestException):
    pass


class MetadataUtil(object):
    def __init__(self, metadata):
        self.metadata = yaml.load(metadata)

    def getEntityDef(self, entityName):
        return self.metadata.get(entityName, None)

    def getKeyFieldDef(self, entityName, keyName=None):
        entityDef = self.getEntityDef(entityName)
        if keyName:
            result = None
            for key in entityDef['key']:
                if keyName == key['name']:
                    result = key
                    break
            return result
        else:
            return entityDef['key']

    def getProperyFeildDef(self, entityName, propertyName=None):
        entityDef = self.getEntityDef(entityName)
        if propertyName:
            result = None
            for property in entityDef['property']:
                if propertyName == property['name']:
                    result = property
                    break
            return result
        else:
            return entityDef['property']

    def getExpandFieldDef(self, entityName):
        entityDef = self.getEntityDef(entityName)
        expandList = entityDef.get('expand', [])
        return expandList

    def getEntityTypeOfName(self, name):
        if name in self.metadata:
            return "single"
        elif name in self.metadata['sets']:
            return "list"
        raise InternalException('Wrong name, not list or single')

    def checkKeyCount(self, entityName):
        entityDef = self.metadata.get(entityName, None)
        if not entityDef:
            return 0
        return len(entityDef.get('key', []))

    def checkKeyName(self, entityName, keyName):
        entityDef = self.metadata.get('entityName', None)
        if not entityDef:
            return False
        found = False
        for key in entityDef['key']:
            if keyName == key['name']:
                found = True
                break
        return found

    def checkFieldValueByType(self, value, type):
        if type == 'int':
            if not re.compile("^[\d]*$").match(value):
                raise MetadataException("Value doesn't match int type")
            return int(value)
        elif type == 'string':
            if len(value) < 2:
                raise MetadataException("Value must contains \" or \' and length > 2")
            if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
                return value[1:-1]
            else:
                raise MetadataException("Mismatch \" or \' for string type")


class XmlConvert(object):
    @staticmethod
    def json_to_xml(tag, json):
        if type(json) is list:
            return XmlConvert.array_to_xml(tag, json)
        elif type(json) is dict:
            return XmlConvert.dict_to_xml(tag, json)
        else:
            return None

    @staticmethod
    def array_to_xml(tag, arr):
        elem = Element(tag)
        for val in arr:
            if type(val) is dict:
                child = XmlConvert.dict_to_xml('item', val)
            else:
                child = Element('item')
                child.text = str(val)
            elem.append(child)
        return elem

    @staticmethod
    def dict_to_xml(tag, d):
        elem = Element(tag)
        for key, val in d.items():
            child = Element(key)
            if type(val) is dict:
                elem.append(XmlConvert.dict_to_xml(key, val))
            elif type(val) is list:
                elem.append(XmlConvert.array_to_xml(key, val))
            else:
                child.text = str(val)
                elem.append(child)
        return elem

    @staticmethod
    def xml_to_dict(xml_text):
        root = fromstring(xml_text)
        result = {}
        for item in root:
            children = item.getchildren()
            if children and children[0].tag == 'item':
                result[item.tag] = XmlConvert.xml_to_array(children)
            else:
                result[item.tag] = item.text
        return result

    @staticmethod
    def xml_to_array(children):
        result = []
        for child in children:
            if child.tag != 'item':
                result.append({child.tag: child.text.strip()})
            else:
                result.append(child.text.strip())
        return result


class RESTEngine(object):
    __restApps = {}
    __metadataUtil = None
    CONTENT_TYPE_JSON = 'application/json'
    CONTENT_TYPE_XML = 'application/xml'
    CONTENT_TYPE_TEXT = 'text/html'
    CONTENT_TYPE_ANY = '*/*'
    DEFAULT_CONTENT_TYPE = CONTENT_TYPE_JSON

    def __init__(self):
        pass

    def registerProcessor(self, entityName, processor):
        processor.setEngine(self)
        processor.bindEntityName(entityName)
        self.__restApps[entityName] = processor

    def getProcessor(self, entityName):
        processor = self.__restApps.get(entityName, None)
        if not processor:
            raise InternalException('No processor found for %s' % entityName)
        return processor

    def getProcessorByEntitySetName(self, entitySetName):
        entityName = self.__metadataUtil.metadata['sets'].get(entitySetName, None)
        if not entityName:
            raise InternalException('No sets defined for %s' % entitySetName)
        return self.getProcessor(entityName)

    def getProcessorByUrlName(self, urlName):
        processor = self.__restApps.get(urlName, None)
        if processor:
            return processor
        return self.getProcessorByEntitySetName(urlName)

    def loadMetadata(self, yamlFile):
        if not yamlFile:
            raise InternalException('No metadata file')
        self.__metadataUtil = MetadataUtil(yamlFile)

    def getMetadataUtil(self):
        return self.__metadataUtil

    def getKeysFromRecord(self, entityName, resultRecord):
        self.__metadataUtil.getKeyFieldDef(entityName)
        expandKeys = {}
        for k in self.__metadataUtil.getKeyFieldDef(entityName):
            expandKeys[k['name']] = resultRecord[k['name']]
        expandKeys = {entityName: expandKeys}
        return expandKeys

    def __getRandomToken(self):
        token = '%d%d' % (int(time.time()), random.randint(0, 999),)
        return token

    @staticmethod
    def getUserContext(request):
        userContextData = request.session.get('userContext', None)
        if userContextData:
            return pickle.loads(userContextData)
        else:
            return None

    @staticmethod
    def setUserContext(request, userContext):
        userContextData = pickle.dumps(userContext)
        request.session['userContext'] = userContextData

    def __checkAndGenerateCsrfToken(self, request, header):
        csrfToken = request.META.get('HTTP_CSRF_TOKEN', None)
        if csrfToken == 'Fetch':
            token = self.__getRandomToken()
            tokenBytes = token.encode('utf-8')
            result = base64.encodebytes(tokenBytes)
            # token = base64.encodestring(self.__getRandomToken())[:-1]
            token = result.decode('utf-8')[:-1]
            expire = time.time() + 3600
            userContext = self.getUserContext(request)
            userContext.csrfTokenInfo = {'token': token, 'expire': expire}
            header['csrf-token'] = token
            self.setUserContext(request, userContext)

    def __validateCsrfToken(self, request):
        csrfToken = request.META.get('HTTP_CSRF_TOKEN', None)
        userContext = self.getUserContext(request)
        csrfTokenInfo = userContext.csrfTokenInfo
        if not csrfToken or not csrfTokenInfo:
            return False
        if time.time() <= csrfTokenInfo['expire'] and csrfToken == csrfTokenInfo['token']:
            return True
        return False

    def __validatePath(self, pathArray):
        tmpArray = pathArray[:-1]
        parentEntityName = None
        for path in tmpArray:
            entityInfo = self.__getEntityInfo(path)
            entityName = entityInfo['entityName']
            keys = entityInfo['keys']
            if not keys:
                raise InternalException('Keys must be provided for %s' % entityInfo['entityName'])
            if parentEntityName:
                possibleExpandItems = self.__metadataUtil.getExpandFieldDef(parentEntityName)
                if path not in possibleExpandItems:
                    raise InternalException('Navigation %s is not valid from %s' % (path, parentEntityName))
            parentEntityName = entityName

    def __process(self, request, pathArray, params):
        allKeys = {}
        result = None
        self.__validatePath(pathArray)
        for entityPath in pathArray:
            # Get information, type values: list or single
            entityInfo = self.__getEntityInfo(entityPath)
            allKeys.update(entityInfo['keys'])
            if entityPath == pathArray[-1]:
                # Only process last entity with all keys from previous entities
                processor = self.getProcessor(entityInfo['entityName'])
                if not processor:
                    raise InternalException('No processor found for %s ' % entityInfo['entityName'])
                result = processor.handle_http_request(request, params, allKeys, entityInfo)
        return result

    def __convertResponse(self, result, content_types):
        response = HttpResponse()
        if self.DEFAULT_CONTENT_TYPE in content_types or self.CONTENT_TYPE_TEXT in content_types or self.CONTENT_TYPE_ANY in content_types:
            response.content = json.dumps(result) if result else ''
            response['Content-Type'] = self.DEFAULT_CONTENT_TYPE
        elif self.CONTENT_TYPE_XML in content_types:
            response.content = tostring(XmlConvert.json_to_xml('xml', result)) if result else ''
            response['Content-Type'] = self.CONTENT_TYPE_XML
        else:
            response.content = 'Required content type %s not supported' % content_types
            response['Content-Type'] = self.CONTENT_TYPE_TEXT
        return response

    def __checkMethodHttpContentTypeAndAccept(self, method, content_types, accepts):
        if method not in ['HEAD', 'GET', 'POST', 'PUT', 'DELETE']:
            raise ParameterErrorException('method %s not allow' % method)
        if method in ['POST', 'PUT']:
            if 'application/json' not in content_types and 'application/xml' not in content_types:
                raise ParameterErrorException('content type not allow')

    def __convertGETparameter(self, request):
        expand = request.GET.get('_expand', None)
        expandArray = [x.strip() for x in expand.split(',')] if expand else []
        order = request.GET.get('_order', None)
        orderArray = [x.strip() for x in order.split(',')] if order else []
        count = request.GET.get('_count', None)
        count = True if count == '' else False
        params = {
            'query': request.GET.get('_query', None),
            'fastquery': request.GET.get('_fastquery', None),
            'expand': expandArray,
            'order': orderArray,
            'page': request.GET.get('_page', None),
            'pnum': request.GET.get('_pnum', 25),
            'count': count,
            'method': request.method
        }
        return params

    def __getEntityInfo(self, urlPath):
        regItem = re.match(r'(\w*)(\(.*\))?', urlPath)
        if not regItem:
            raise ParameterErrorException('Wrong Url pattern')
        entitySet = regItem.group(1)
        if not entitySet:
            raise ParameterErrorException('No entity set name found')
        entityName = self.__metadataUtil.metadata['sets'].get(entitySet, None)
        if not entityName:
            raise ParameterErrorException('Invalid entity name')
        entityDef = self.__metadataUtil.metadata.get(entityName, None)
        if not entityDef:
            raise ParameterErrorException('Entity metadata not found')
        keys = {}
        if regItem.group(2):
            keysString = regItem.group(2)[1:-1]
            keysArray = keysString.split(',')
            if len(keysArray) == 1:
                keyDefs = self.__metadataUtil.getKeyFieldDef(entityName)
                if len(keyDefs) != 1:
                    raise ParameterErrorException('Number of key field mismatch')
                value = self.__metadataUtil.checkFieldValueByType(keysArray[0], keyDefs[0]['type'])
                if not value:
                    raise ParameterErrorException('Wrong key value')
                keys[entityName] = {keyDefs[0]['name']: value}
            else:
                keyPairs = {}
                for key in keysArray:
                    keyPair = key.split('=')
                    if len(keyPair) < 2:
                        raise ParameterErrorException("Mutiple key given but doesn't contains = ")
                    key, value = keyPair[0].strip(), keyPair[1].strip()
                    keyDef = self.__metadataUtil.getKeyFieldDef(entityName, key)
                    if not keyDef:
                        raise ParameterErrorException('Wrong key')
                    value = self.__metadataUtil.checkFieldValueByType(value, keyDef['type'])
                    if not value:
                        raise ParameterErrorException('Wrong key value')
                    keyPairs[keyDef['name']] = value
                keys[entityName] = keyPairs
            queryType = "single"
        else:
            queryType = "list"
        return {
            'entitySet': entitySet,
            'entityName': entityName,
            'queryType': queryType,
            'keys': keys
        }

    def handle(self, request, path):
        # Create default user context if not available
        userContext = self.getUserContext(request)
        if not userContext:
            userContext = UserContext()
            self.setUserContext(request, userContext)
        # Split request entities
        pathArray = path.split('/')
        # log.info('Request path: %s' % pathArray)
        # Default http status
        http_response_status = 404
        # Response header
        http_response_header = {}
        requestContentTypes = request.META.get('CONTENT_TYPE', RESTEngine.DEFAULT_CONTENT_TYPE).split(',')
        requiredContentTypes = request.META.get('HTTP_ACCEPT', RESTEngine.DEFAULT_CONTENT_TYPE).split(',')
        if path == '' or path is None:
            availableEntities = []
            for k, v in self.getMetadataUtil().metadata.get('sets', None).items():
                availableEntities.append(k)
            response = self.__convertResponse(availableEntities, requiredContentTypes)
            return response
        elif path == '_metadata':
            response = self.__convertResponse(self.getMetadataUtil().metadata, requiredContentTypes)
            return response
        method = request.method
        self.__checkMethodHttpContentTypeAndAccept(method, requestContentTypes, requiredContentTypes)
        if method == 'GET' or method == 'HEAD':
            params = self.__convertGETparameter(request) if method == 'GET' else {}
            self.__checkAndGenerateCsrfToken(request, http_response_header)
            result = self.__process(request, pathArray, params)
            http_response_status = 200
        else:
            # For POST PUT DELETE
            if not self.__validateCsrfToken(request):
                raise NoAuthException('csrf token error')
            result = self.__process(request, pathArray, None)
            if method == 'POST':
                http_response_status = 201
            else:
                http_response_status = 204
        response = self.__convertResponse(result, requiredContentTypes)
        response.status_code = http_response_status
        for k, v in http_response_header.items():
            response[k] = v
        return response


class RESTProcessor(object):
    __engine = None
    __baseDjangoModel = None
    __bindEntityName = None

    def __init__(self, baseDjangoModel):
        self.__baseDjangoModel = baseDjangoModel

    def setEngine(self, engine):
        self.__engine = engine

    def getEngine(self):
        return self.__engine

    def bindEntityName(self, entityName):
        self.__bindEntityName = entityName

    def getBindEntityName(self):
        return self.__bindEntityName

    def __getSelfKey(self, keys):
        key = keys.get(self.__bindEntityName, None)
        if not key:
            raise InternalException('Framework error, key is not filled')
        return key

    def getMappedFieldName(self, fieldName):
        return fieldName

    def __getSelfKeyValue(self, keys, column):
        return self.__getSelfKey(keys).get(column, None)

    def __validateExpandItem(self, entityName, expandItemList):
        for expandItem in expandItemList:
            if expandItem not in self.__engine.getMetadataUtil().getExpandFieldDef(entityName):
                raise ParameterErrorException('Expand item %s not valid' % expandItem)
        return True

    def __expandItemProcess(self, request, expandItem, parentItemkeys):
        processor = self.__engine.getProcessorByUrlName(expandItem)
        qt = self.__engine.getMetadataUtil().getEntityTypeOfName(expandItem)
        result = processor.handle_http_request(request, {}, parentItemkeys, {'queryType': qt})
        return result

    def __formatDateTime(self, dt, format="%Y-%m-%d %H:%M:%S"):
        return str(timezone.localtime(dt).strftime(format))

    def __populateToJson(self, jsonDict, djangoModel, fields):
        for field in fields:
            if type(field) is tuple:
                jfield = field[0]
                mfield = field[1]
            else:
                mfield = jfield = field
            if callable(mfield):
                value = mfield(djangoModel)
            elif type(mfield) is dict:
                value = mfield.get('value', None)
            else:
                value = eval('djangoModel.%s' % mfield)
            if type(value) is datetime.datetime:
                value = self.__formatDateTime(value)
            if value:
                jsonDict[jfield] = value
        return jsonDict

    def handle_http_request(self, request, params, keys, entityInfo):
        result = None
        queryType = entityInfo.get('queryType', None)
        if request.method == 'GET':
            expandArray = params.get('expand', [])
            query = params.get('query', None)
            entityName = entityInfo.get('entityName', None)
            self.__validateExpandItem(entityName, expandArray)
            if queryType == 'single':
                result = self.getSingle(request, keys)
                # Add expand item
                for expandItem in expandArray:
                    result[expandItem] = self.__expandItemProcess(request, expandItem, keys)
            elif queryType == 'list':
                if query:
                    try:
                        parser = Parser(query)
                        conditions = parser.toDict(parser.parse())
                        params['conditions'] = conditions
                        q = self.parseToQObject(conditions)
                        params['q'] = q
                    except Exception as e:
                        raise ParameterErrorException('Error when parsing query url: %s' % str(e))
                result = self.getList(request, keys, **params)
                if type(result) is list and expandArray:
                    for resultRecord in list(result):
                        expandKeys = self.__engine.getKeysFromRecord(entityName, resultRecord)
                        for expandItem in expandArray:
                            resultRecord[expandItem] = self.__expandItemProcess(request, expandItem, expandKeys)
        elif request.method == 'HEAD':
            result = self.head(request)
        elif request.method == 'POST':
            result = self.post(request)
        elif request.method == 'PUT':
            if not keys:
                raise ParameterErrorException('Missing key')
            result = self.put(request, keys)
        elif request.method == 'DELETE':
            if not keys:
                raise ParameterErrorException('Missing key')
            result = self.delete(request, keys)
        else:
            raise NotImplementedException('')
        return self.postProcessResult(result, queryType, request.method)

    def getBaseQuery(self):
        return None

    def getFastQuery(self, text):
        return None

    def getDjangoModelCls(self):
        return None

    def getBaseDjangoModel(self):
        return self.__baseDjangoModel

    def getListByKey(self, keys):
        return None

    def getList(self, request, keys, **kwargs):
        userContext = RESTEngine.getUserContext(request)
        query = self.getBaseQuery()
        if not query:
            query = Q()
        fastQueryText = kwargs.get('fastquery', None)
        if fastQueryText:
            q = self.getFastQuery(fastQueryText)
            if q:
                query.add(q, Q.AND)
        else:
            q = kwargs.get('q', None)
            if q:
                query.add(q, Q.AND)
        djangoresult = None
        if keys:
            djangoresult = self.getListByKey(keys)
            if djangoresult and type(djangoresult) is not QuerySet:
                raise InternalException('getListByKey result must be QuerySet')
        order = kwargs.get('order', [])
        order = tuple(order)
        if type(djangoresult) is QuerySet:
            djangoresult = djangoresult.filter(query).order_by(*order)
        else:
            djangoModel = self.getDjangoModelCls() if not self.__baseDjangoModel else self.__baseDjangoModel
            if not djangoModel:
                raise InternalException('Model not defined')
            djangoresult = djangoModel.objects.filter(query).order_by(*order)
        if not djangoresult:
            return []
        page = kwargs.get('page', None)
        pnum = kwargs.get('pnum', None)
        pagingresult = djangoresult
        if page:
            paginator = Paginator(djangoresult, pnum)
            try:
                pagingresult = paginator.page(page)
            except PageNotAnInteger:
                pagingresult = paginator.page(1)
            except EmptyPage:
                pagingresult = paginator.page(paginator.num_pages)
        if kwargs.get('count', False):
            return len(pagingresult)
        finalresult = []
        for r in pagingresult:
            record = self.convertData(r, None)
            finalresult.append(record)
        return finalresult

    def getSingle(self, request, keys):
        djangoModel = self.getDjangoModelCls() if not self.__baseDjangoModel else self.__baseDjangoModel
        if not djangoModel:
            raise InternalException('Model not defined')
        key = self.__getSelfKey(keys)
        q = Q()
        for k, v in key.items():
            # Chance to get real db model field name
            k = self.getMappedFieldName(k)
            q.add(self.buildQobject(k, '=', v), Q.AND)
        baseQ = self.getBaseQuery()
        if baseQ:
            q.add(baseQ, Q.AND)
        model = djangoModel.objects.get(q)
        userContext = RESTEngine.getUserContext(request)
        record = self.convertData(model, None)
        return record

    def post(self, request):
        raise NotImplementedException("Not Implemented")

    def put(self, request, keys):
        raise NotImplementedException("Not Implemented")

    def head(self, request):
        return {}

    def delete(self, request, keys):
        raise NotImplementedException("Not Implemented")

    def getPopulateFieldMapping(self):
        """
        Array list contains field name, each object can be:
        1. Simple string, e.g. 'name' -> get name field from model object
        2. Tuple object, e.g. ('name', 'name1') -> get name1 field from model object and set to json as name
        3. Tuple object with function, e.g. ('name', lambda x:x.lastName + x.firstName) -> lambda or function will be called to get result
        4. Dict object, e.g. {'value':'const value'} -> set constant value to json object
        :return: array list
        """
        return None

    def convertData(self, model, language=None):
        mapping = self.getPopulateFieldMapping()
        if mapping:
            record = {}
            self.__populateToJson(record, model, mapping)
            return record
        return {}

    def parseToQObject(self, conditions):
        opt = conditions.get('opt', None)
        if not opt:
            return None
        if not (opt == 'and' or opt == 'or'):
            field = conditions.get('field', None)
            # Chance to get db model field name
            field = self.getMappedFieldName(field)
            value = conditions.get('value', None)
            return self.buildQobject(field, opt, value)
        else:
            left = conditions.get('left', None)
            right = conditions.get('right', None)
            qleft = self.parseToQObject(left)
            qright = self.parseToQObject(right)
            q2 = Q()
            q2.add(qleft, opt.upper())
            q2.add(qright, opt.upper())
            return q2

    def buildQobject(self, fieldname, opt, low, high=None):
        if not low:
            return
        q = Q()
        ao = Q.AND
        conKey = fieldname
        # Operator mapping
        if opt == '%':
            conKey = ''.join([fieldname, '__icontains'])
            q.add(Q(**{conKey: low}), ao)
        elif opt == '!%':
            conKey = ''.join([fieldname, '__icontains'])
            q.add(~Q(**{conKey: low}), ao)
        elif opt == '=':
            q.add(Q(**{conKey: low}), ao)
        elif opt == '!=':
            q.add(~Q(**{conKey: low}), ao)
        elif opt == '<':
            conKey = ''.join([fieldname, '__lt'])
            q.add(Q(**{conKey: low}), ao)
        elif opt == '<=':
            conKey = ''.join([fieldname, '__lte'])
            q.add(Q(**{conKey: low}), ao)
        elif opt == '>':
            conKey = ''.join([fieldname, '__gt'])
            q.add(Q(**{conKey: low}), ao)
        elif opt == '>=':
            conKey = ''.join([fieldname, '__gte'])
            q.add(Q(**{conKey: low}), ao)
        elif opt == '@':
            rq = Q()
            conKey = ''.join([fieldname, '__gte'])
            q1 = Q(**{conKey: low})
            conKey = ''.join([fieldname, '__lte'])
            q2 = Q(**{conKey: high})
            rq.add(q1, Q.AND)
            rq.add(q2, Q.AND)
            q.add(rq, Q.AND)
        return q

    def postProcessResult(self, result, queryType, method):
        return result


def requireProcess(need_login=True, need_decrypt=True):
    def decorate(view_func):
        def errorResponse(status, message):
            # log.error('%s %s' % (message, traceback.extract_stack(limit=5)))
            content = {'error': message}
            response = HttpResponse(status=status, content=json.dumps(content))
            response['Content-Type'] = 'application/json'
            return response

        def check(*args, **kwargs):
            request = args[0]
            if request.method == 'OPTIONS':
                response = HttpResponse()
                # response['Access-Control-Allow-Origin'] = '*'
                # response['Access-Control-Allow-Headers'] = 'Content-Type'
                return response
            requestContentTypes = request.META.get('CONTENT_TYPE', RESTEngine.DEFAULT_CONTENT_TYPE).split(',')
            body = request.body
            if need_decrypt:
                pass
                # body = decrypt(body, True)
            if body:
                if 'application/json' in requestContentTypes:
                    if type(body) is bytes:
                        body = body.decode('utf-8')
                    try:
                        body = json.loads(body)
                    except Exception as e:
                        return errorResponse(400, 'Invalid request %s' % str(e))
                elif 'application/xml' in requestContentTypes:
                    body = XmlConvert.xml_to_dict(request.body)
            request.jsonBody = body
            if need_login:
                pass
                # userId = body.get('userId', None)
                # if not userId:
                #     return errorResponse(403, 'Invalid login')
                # if User.objects.filter(userId=userId).count() == 0:
                #     return errorResponse(403, 'Invalid user')
            try:
                return view_func(*args, **kwargs)
            except BadRequestException as e:
                return errorResponse(400, str(e))
            except ObjectDoesNotExist as e:
                return errorResponse(404, str(e))
            except NotImplementedException as e:
                return errorResponse(501, str(e))
            except NoAuthException as e:
                return errorResponse(403, str(e))
            except InternalException as e:
                return errorResponse(500, 'Internal server error: %s' % str(e))
            except Exception as e:
                return errorResponse(500, str(e))

        return check

    return decorate
