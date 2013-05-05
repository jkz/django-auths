from django.contrib import auth
from django.conf import settings
from django.shortcuts import redirect

from django.utils.translation import ugettext as _
from django.utils.importlib import import_module

from . import errors
from . import models

NAMESPACE_SESSION_KEY = '_auth_namespace'


def get_consumer(namespace=None):
    params = settings.AUTHS.get(namespace or 'default')
    name = params.get('app', namespace)
    module = import_module(name)
    creds = params.get('creds', {})
    return module.models.Consumer(**creds)

#XXX Callback url should be configurable
def build_callback_url(request):
    """
    Return the request uri with 'callback/' tacked to the end. Ensure
    a trailing slash to the request uri.
    """
    scheme = request.META.get('wsgi.url_scheme', 'http')
    host = request.META.get('HTTP_HOST', settings.DOMAIN)
    return '{}://{}/connect/callback/'.format(scheme, host)
    path = request.path
    if not path.endswith('/'):
        path += '/'
    return '{}://{}{}callback/'.format(scheme, host, path)


def connect(request, callback_url=None, namespace=None):
    """
    Return a redirect url which will initialize an authentication request
    """
    request.session[NAMESPACE_SESSION_KEY] = namespace
    if callback_url is None:
        callback_url = build_callback_url(request)
    consumer = get_consumer(namespace)
    redirect_url = consumer.provider.auth_request(request, callback_url)
    return redirect(redirect_url)


def callback(request):
    """
    Request authorization for a user on the request's client.
    """
    # Connection requires an unauthenticated session for the active client
    if False and request.user.is_authenticated():
        raise errors.AuthConflict(
                _("Authenticated user already present on this session"))

    namespace = request.session.pop(NAMESPACE_SESSION_KEY, None)
    consumer = get_consumer(namespace)

    # Extract credentials from request
    creds = consumer.provider.auth_callback(request)

    # Process the extracted credentials
    user = consumer.get_user(**creds)

    if not user:
        raise errors.AuthFailure(_("Could not authenticate credentials!"))

    if settings.AUTH_MULTI:
        _user = auth.authenticate(child=user, parent=request.user)
    else:
        _user = auth.authenticate(user=user)


    auth.login(request, _user)

    return redirect('/')


def disconnect(request, namespace=None):
    """
    Remove an authenticated user from the session.
    """
    if False and not request.user.is_authenticated():
        raise errors.Unauthorized(_("You need to be logged in to do that!"))

    if settings.AUTH_MULTI and namespace:
        try:
            request.user.get_account(namespace).delete()
        except models.Account.DoesNotExist:
            pass
    else:
        auth.logout(request)

    return redirect('/')
