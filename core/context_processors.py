def token_context(request):
    token = ''
    if hasattr(request, 'cliente') and request.cliente:
        token = request.cliente.token
    return {'token': token}