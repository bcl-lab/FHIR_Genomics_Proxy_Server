'''
This is a http-forward server which wrap the json data with apply of privacy_policy
To security, we separate this proxy with original server and privacy_server.
So this file is designed solely intend to pass http request.

It deals with several circumstances:

for auth request, simply redirect or send http request forwarding
for api request, check the get response and pick up those resource seperately as either a single one
or multiple bundles. If it is a patient-related resource, we can ask privacy_policy from privacy_server
and wrap it into json_data

To use this proxy_server, just let client apps point to this base_url (http://localhost:9090 in this demo)
the app will see exactly the same thing as did before but some patient privacy_policy will "forbid" client
from get full responded data.

TODO : xml parsing support (to wrap up xml data)
'''

import io
import requests
import json
import xmltodict as xml

from config import SERVER_BASE,PRIVACY_BASE
from flask import Flask
from flask import request,redirect,make_response,after_this_request
from urllib import urlencode
from common import filter_policy


dispatcher = Flask(__name__)

KNOWN_HTTP_METHOD=['GET','POST','PUT','DELETE']
MUST_PARSE_ARGS_HEADER=['Authorization','Accept']
KNOWN_JSON_TYPE=['application/json']
KNOWN_XML_TYPE=['application/xml','application/xml; charset=utf-8']

class ForwardError(Exception):
    '''
    Leave to extension: Forward Error
    '''
    pass

class UnderDevError(Exception):
    '''
    This is just an Error Type
    '''
    pass

def parse_request_headers():
    '''
    Here we need to parse auth_headers from client apps
    :return: request.headers
    '''
    headers = {}
    for k,v in request.headers:
        if k in MUST_PARSE_ARGS_HEADER:
            headers[k] = v
    return headers


def wrap_data(resource,auth_header):
    '''
    The proxy aims to filter json/xml data
    Here is where the program deals with that
    :param resource: Response class, it will contain all info the proxy received at remote server
           auth_header: We must ask data_server some sufficient info we need to wrap up the data
    :return: the 'wrapped' json/xml data where the privacy policy is applied

    Note we separate this part from remote server is for better extension and maintenance
    (If someone can see full data or some requests needn't apply policy_wrapper)
    '''
    # To do : xml data is not fully supported since we did not figure out how to check data_type in
    # Response class
    if (resource.status_code!= 200):
        return resource._content
    print resource.headers['Content-type']
    if (resource.headers['Content-type'] in KNOWN_JSON_TYPE):
        # Do as json-type
        #print "1\n"
        try:
            wrapped_content=filter_policy(json.dumps(resource.json()),auth_header)
            return wrapped_content
        except:
            return resource._content
    elif (resource.headers['Content-type'] in KNOWN_XML_TYPE):
        # Do as xml-data ,with the help of xmltodict
        try:
            json_data = xml.parse(resource._content, process_namespaces=True)
            wrapped_content=filter_policy(json_data,auth_header)
            return wrapped_content
        except:
            return resource._content
    else:
        raise ForwardError



# This api method is designed to get superadministrative access to Resources (i.e. all can be shwon)
@dispatcher.route('/api/neprivacy/<path:request_url>', methods=KNOWN_HTTP_METHOD)
def request_handler_noprivacy(request_url):

    @after_this_request
    def add_header(response):
        try:
            response.headers['Content-type'] = resp.headers['Content-type']
            response.headers['HOST'] = resp.headers['HOST']
        except:
            pass
        return response

    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    auth_header= parse_request_headers()
    resp = requests.request(method= request.method, url='%s/api/%s?%s' %(SERVER_BASE,request_url,urlencode(request.args, doseq=True)), headers=auth_header, data=request.form)
    #print '%s/api/%s?%s' %(PRIVACY_BASE,request_url,urlencode(request.at'rgs, doseq=True))
    try:
        return resp._content
    except:
        raise UnderDevError

@dispatcher.route('/api/<path:request_url>', methods=KNOWN_HTTP_METHOD)

def request_handler(request_url):
    '''
    This is http forwarding part, yet it has little trick to wrap json data before
    these resources was sent back
    :param request_url:
    :return:
    '''
    @after_this_request
    def add_header(response):
        try:
            response.headers['Content-type'] = resp.headers['Content-type']
            response.headers['HOST'] = resp.headers['HOST']
        except:
            pass
        return response
    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    if request.method == 'GET':
        auth_header = parse_request_headers()
        resp = requests.get('%s/api/%s?%s' %(SERVER_BASE, request_url,urlencode(request.args,doseq=True)), headers=auth_header)
        #Here is the API dealing with received resource of json data
        # TO DO : xml parser is not tested well yet.
        return wrap_data(resp,auth_header)
    elif request.method == 'POST':
        auth_header = parse_request_headers()
        resp = requests.post('%s/api/%s?%s' %(SERVER_BASE, request_url,urlencode(request.args,doseq=True)), data=request.form, headers=auth_header)
        return resp._content
    elif request.method == 'PUT':
        auth_header = parse_request_headers()
        resp = requests.put('%s/api/%s?%s' %(SERVER_BASE, request_url,urlencode(request.args,doseq=True)), data=request.form, headers=auth_header)
        return resp._content
    elif request.method == 'DELETE':
        auth_header = parse_request_headers()
        resp = requests.delete('%s/api/%s?%s' %(SERVER_BASE, request_url,urlencode(request.args,doseq=True)), headers=auth_header)
        return resp._content
    else:
        raise ForwardError




@dispatcher.route('/auth/<path:request_url>', methods=KNOWN_HTTP_METHOD)
def request_forwarder(request_url):
    '''
    This is the authorization route
    simply in demo we put forward this request while saving the cookies.
    :param request_url:
    :return:
    '''
    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    if request.method=='POST':
        #print type(request.form)
        resp = requests.post('%s/auth/%s' %(SERVER_BASE,request_url), data=request.form)
        return resp.text
    elif request.method=='GET':
        #print request.session.user
        resp=redirect('%s/auth/%s?%s'% (SERVER_BASE,request_url,urlencode(request.args)))
        return resp
    else:
        raise ForwardError


@dispatcher.route('/Privacy/<path:request_url>', methods = KNOWN_HTTP_METHOD)
def privacylist_request(request_url):
    '''
    Well, for request to Privacy_Server, at this proxy server we will only redirect and send request to
    remote Privacy_Server, and then send the response back to client side. The protection and management will
    be settled in Privacy_Server
    :param request_url:
    :return:
    '''
    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    auth_header= parse_request_headers()
    resp = requests.request(method= request.method, url='%s/Privacy/%s?%s' %(PRIVACY_BASE,request_url,urlencode(request.args, doseq=True)), headers=auth_header, data=request.form)
    try:
        return resp._content
    except:
        raise UnderDevError

@dispatcher.route('/Privacy', methods = KNOWN_HTTP_METHOD)
def privacy_request():
    '''
    Well, for request to Privacy_Server, at this proxy server we will only redirect and send request to
    remote Privacy_Server, and then send the response back to client side. The protection and management will
    be settled in Privacy_Server
    :param request_url:
    :return:
    '''
    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    auth_header= parse_request_headers()
    resp = requests.request(method= request.method, url='%s/Privacy?%s' %(PRIVACY_BASE,urlencode(request.args, doseq=True)), headers=auth_header, data=request.form)
    try:
        return resp._content
    except:
        raise UnderDevError


@dispatcher.route('/<path:redirect_path>', methods = KNOWN_HTTP_METHOD)
def proxy_pass(redirect_path):
    '''
    Normally pass unassigned request to data_server
    :param redirect_path:
    :return:
    '''
    if request.method not in KNOWN_HTTP_METHOD:
        raise ForwardError
    auth_header= parse_request_headers()
    resp = requests.request(method= request.method, url='%s/%s?%s' %(SERVER_BASE,redirect_path,urlencode(request.args, doseq=True)), headers=auth_header, data=request.form)
    try:
        return resp._content
    except:
        raise UnderDevError

if __name__ == '__main__':
    dispatcher.run(host='127.0.0.1',port=9090,debug=True)