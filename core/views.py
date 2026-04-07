from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from datetime import datetime, date, timedelta
import json
import csv
import mercadopago
import os

from .models import Cliente, Pagamento, Insumo, Venda, Gasto

# ── CONFIG ───────────────────────────────────────────────────────────────────
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from datetime import datetime, date, timedelta
import json
import csv
import mercadopago
import os

from .models import Cliente, Pagamento, Insumo, Venda, Gasto
from django.views.decorators.csrf import csrf_exempt

# ── CONFIG ───────────────────────────────────────────────────────────────────
# Priorize as variáveis de ambiente, mas mantenha o fallback para testes
MP_ACCESS_TOKEN = os.environ.get('MP_ACCESS_TOKEN', 'APP_USR-8767681020570956-040711-2e650ee4dfe1aeb4d97588b53dbd1587-3319733167')
VALOR_MENSAL = 20.00
SITE_URL = os.environ.get('SITE_URL', 'https://fibreless-disparagingly-aubri.ngrok-free.dev') # Remova a barra final se houver

def get_mp():
    return mercadopago.SDK(MP_ACCESS_TOKEN)

# ── LANDING / REGISTRO ───────────────────────────────────────────────────────

def landing(request):
    return render(request, 'landing.html')

@csrf_exempt
def registrar(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nome = data.get('nome', '').strip()
            email = data.get('email', '').strip()
            cpf = data.get('cpf', '').strip()

            if not nome or not email or not cpf:
                return JsonResponse({'success': False, 'error': 'Preencha todos os campos.'}, status=400)

            cliente = Cliente.objects.create(nome=nome, email=email, cpf_pix=cpf)
            pagamento = _criar_pagamento_pix(cliente)

            return JsonResponse({
                'success': True,
                'token': cliente.token,
                'pagamento_id': pagamento.id,
                'qr_code_base64': pagamento.qr_code_base64,
                'pix_copia_cola': pagamento.pix_copia_cola,
            })
        except Exception as e:
            import traceback
            print("=== ERRO REGISTRAR ===")
            traceback.print_exc()  # ← mostra o erro completo no terminal
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)

def _criar_pagamento_pix(cliente):
    sdk = get_mp()
    
    cpf_limpo = cliente.cpf_pix.replace('.', '').replace('-', '').replace(' ', '')
    
    payment_data = {
        "transaction_amount": float(VALOR_MENSAL),
        "description": "GestãoPro — Acesso 30 dias",
        "payment_method_id": "pix",
        "payer": {
            "email": cliente.email,
            "first_name": cliente.nome.split()[0] if cliente.nome else "Cliente",
            "identification": {
                "type": "CPF",
                "number": cpf_limpo if len(cpf_limpo) == 11 else "00000000000"
            }
        },
        "external_reference": str(cliente.token),
    }

    if SITE_URL and not SITE_URL.startswith('http://127') and not SITE_URL.startswith('http://localhost'):
        payment_data["notification_url"] = f"{SITE_URL}/webhook/mercadopago/"

    result = sdk.payment().create(payment_data)
    payment = result.get("response", {})
    
    # ← ADICIONA ISSO
    print("=== RESPOSTA MP ===")
    print("status:", payment.get("status"))
    print("status_detail:", payment.get("status_detail"))
    print("cause:", payment.get("cause"))          # ← adiciona
    print("message:", payment.get("message"))      # ← adiciona
    print("error:", payment.get("error")) 
    print("point_of_interaction:", payment.get("point_of_interaction"))
    print("===================")
    
    transaction_data = payment.get("point_of_interaction", {}).get("transaction_data", {})
    
    qr_base64 = transaction_data.get("qr_code_base64", "").replace('\n', '').replace('\r', '').strip()
    qr_code   = transaction_data.get("qr_code", "")

    pagamento = Pagamento.objects.create(
        cliente=cliente,
        mp_payment_id=str(payment.get("id", "")),
        valor=VALOR_MENSAL,
        status='pendente',
        qr_code=qr_code,
        qr_code_base64=qr_base64,
        pix_copia_cola=qr_code,
    )
    return pagamento

# ── VERIFICAR PAGAMENTO ───────────────────────────────────────────────────────

def verificar_pagamento(request, token):
    """Polling: verifica se o pagamento foi aprovado"""
    cliente = get_object_or_404(Cliente, token=token)
    if cliente.acesso_valido:
        return JsonResponse({'pago': True, 'token': cliente.token})
    return JsonResponse({'pago': False})


# ── WEBHOOK MERCADO PAGO ──────────────────────────────────────────────────────

@csrf_exempt
def webhook_mercadopago(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # O ID vem dentro de ['data']['id'] no seu print do ngrok
            mp_id = data.get('data', {}).get('id')

            if mp_id:
                sdk = get_mp()
                result = sdk.payment().get(mp_id)
                payment = result.get("response", {})
                
                status = payment.get("status")
                # O external_reference que você enviou no registrar()
                token = payment.get("external_reference")

                print(f"--- Webhook Recebido: Pagamento {mp_id} Status: {status} ---")

                if status == "approved" and token:
                    cliente = Cliente.objects.filter(token=token).first()
                    if cliente and not cliente.ativo: # Evita reprocessar se já estiver ativo
                        cliente.ativo = True
                        # Adiciona 30 dias de acesso
                        cliente.acesso_ate = timezone.now() + timedelta(days=30)
                        cliente.save()
                        
                        # Atualiza o status do pagamento no seu banco
                        Pagamento.objects.filter(mp_payment_id=str(mp_id)).update(status='aprovado')
                        print(f"✅ ACESSO LIBERADO: {cliente.nome}")
            
        except Exception as e:
            print(f"❌ Erro no Webhook: {e}")
            
        return HttpResponse(status=200)
    return HttpResponse(status=405)


# ── RENOVAÇÃO ─────────────────────────────────────────────────────────────────

def renovar(request, token):
    """Gera novo PIX para renovação"""
    cliente = get_object_or_404(Cliente, token=token)
    if request.method == 'POST':
        try:
            pagamento = _criar_pagamento_pix(cliente)
            return JsonResponse({
                'success': True,
                'qr_code_base64': pagamento.qr_code_base64,
                'pix_copia_cola': pagamento.pix_copia_cola,
                'pagamento_id': pagamento.id,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


# ── MIDDLEWARE DE ACESSO ──────────────────────────────────────────────────────

def acesso_required(view_func):
    """Decorator que verifica se o cliente tem acesso válido"""
    def wrapper(request, token, *args, **kwargs):
        cliente = get_object_or_404(Cliente, token=token)
        if not cliente.acesso_valido:
            return render(request, 'renovar.html', {
                'cliente': cliente,
                'token': token,
                'expirado': cliente.ativo and not cliente.acesso_valido,
            })
        request.cliente = cliente
        return view_func(request, token, *args, **kwargs)
    return wrapper


# ── VIEWS DO SISTEMA (com token) ─────────────────────────────────────────────

@acesso_required
def home(request, token):
    cliente = request.cliente
    hoje = date.today()
    vendas_hoje = Venda.objects.filter(cliente=cliente, data_hora__date=hoje).aggregate(
        total=Sum('preco_venda'))['total'] or 0
    gastos_hoje = Gasto.objects.filter(cliente=cliente, data_hora__date=hoje).aggregate(
        total=Sum('valor'))['total'] or 0
    insumos_count = Insumo.objects.filter(cliente=cliente, ativo=True).count()
    vendas_count = Venda.objects.filter(cliente=cliente, data_hora__date=hoje).count()
    return render(request, 'home.html', {
        'token': token, 'cliente': cliente,
        'vendas_hoje': vendas_hoje, 'gastos_hoje': gastos_hoje,
        'insumos_count': insumos_count, 'vendas_count': vendas_count,
    })


@acesso_required
def insumos(request, token):
    cliente = request.cliente
    lista = Insumo.objects.filter(cliente=cliente, ativo=True)
    return render(request, 'insumos.html', {'token': token, 'cliente': cliente, 'insumos': lista})


@acesso_required
def cadastrar_insumo(request, token):
    if request.method == 'POST':
        try:
            cliente = request.cliente
            data = json.loads(request.body)
            insumo = Insumo.objects.create(
                cliente=cliente,
                nome=data['nome'],
                preco_custo=Decimal(str(data.get('preco_custo', 0))),
                preco=Decimal(str(data['preco'])),
                quantidade=Decimal(str(data['quantidade'])),
                unidade=data.get('unidade', 'un'),
            )
            margem = insumo.margem
            return JsonResponse({'success': True, 'insumo': {
                'id': insumo.id, 'nome': insumo.nome,
                'preco_custo': float(insumo.preco_custo), 'preco': float(insumo.preco),
                'quantidade': float(insumo.quantidade), 'unidade': insumo.unidade,
                'data_hora': insumo.data_hora.strftime('%d/%m/%Y %H:%M'),
                'valor_total': float(insumo.valor_total),
                'margem': round(margem, 1) if margem is not None else None,
            }})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@acesso_required
def excluir_insumo(request, token, pk):
    if request.method == 'POST':
        insumo = get_object_or_404(Insumo, pk=pk, cliente=request.cliente)
        insumo.ativo = False
        insumo.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@acesso_required
def vendas(request, token):
    cliente = request.cliente
    lista = Venda.objects.filter(cliente=cliente).select_related('insumo')
    insumos_disp = Insumo.objects.filter(cliente=cliente, ativo=True, quantidade__gt=0)
    return render(request, 'vendas.html', {
        'token': token, 'cliente': cliente, 'vendas': lista, 'insumos': insumos_disp
    })


@acesso_required
def cadastrar_venda(request, token):
    if request.method == 'POST':
        try:
            cliente = request.cliente
            data = json.loads(request.body)
            insumo = get_object_or_404(Insumo, pk=data['insumo_id'], cliente=cliente, ativo=True)
            qtd = Decimal(str(data['quantidade']))
            preco_venda = Decimal(str(data['preco_venda']))
            desconto = Decimal(str(data.get('desconto', 0)))

            if qtd > insumo.quantidade:
                return JsonResponse({'success': False,
                    'error': f'Estoque insuficiente. Disponível: {insumo.quantidade} {insumo.unidade}'}, status=400)
            if insumo.preco_custo > 0 and preco_venda < insumo.preco_custo:
                return JsonResponse({'success': False,
                    'error': f'Preço de venda menor que o custo (R$ {insumo.preco_custo})'}, status=400)

            venda = Venda.objects.create(
                cliente=cliente, insumo=insumo,
                quantidade_vendida=qtd, preco_venda=preco_venda, desconto=desconto,
                forma_pagamento=data.get('forma_pagamento', 'dinheiro'),
                cliente_nome=data.get('cliente', ''), observacao=data.get('observacao', ''),
            )
            insumo.quantidade -= qtd
            insumo.save()

            FORMAS = {'dinheiro': 'Dinheiro', 'pix': 'PIX', 'cartao_credito': 'Cartão Crédito',
                      'cartao_debito': 'Cartão Débito', 'outro': 'Outro'}
            return JsonResponse({'success': True, 'venda': {
                'id': venda.id, 'insumo': insumo.nome,
                'quantidade': float(venda.quantidade_vendida), 'preco_venda': float(venda.preco_venda),
                'desconto': float(venda.desconto), 'valor_total': float(venda.valor_total),
                'forma_pagamento': FORMAS.get(venda.forma_pagamento, venda.forma_pagamento),
                'cliente': venda.cliente_nome, 'data_hora': venda.data_hora.strftime('%d/%m/%Y %H:%M'),
                'estoque_restante': float(insumo.quantidade), 'unidade': insumo.unidade,
            }})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@acesso_required
def excluir_venda(request, token, pk):
    if request.method == 'POST':
        venda = get_object_or_404(Venda, pk=pk, cliente=request.cliente)
        venda.insumo.quantidade += venda.quantidade_vendida
        venda.insumo.save()
        venda.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@acesso_required
def gastos(request, token):
    cliente = request.cliente
    lista = Gasto.objects.filter(cliente=cliente)
    return render(request, 'gastos.html', {'token': token, 'cliente': cliente, 'gastos': lista})


@acesso_required
def cadastrar_gasto(request, token):
    if request.method == 'POST':
        try:
            cliente = request.cliente
            data = json.loads(request.body)
            gasto = Gasto.objects.create(
                cliente=cliente, descricao=data['descricao'],
                valor=Decimal(str(data['valor'])),
                categoria=data.get('categoria', 'outro'),
                observacao=data.get('observacao', ''),
            )
            return JsonResponse({'success': True, 'gasto': {
                'id': gasto.id, 'descricao': gasto.descricao, 'valor': float(gasto.valor),
                'categoria': gasto.get_categoria_display(), 'categoria_raw': gasto.categoria,
                'data_hora': gasto.data_hora.strftime('%d/%m/%Y %H:%M'), 'observacao': gasto.observacao,
            }})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@acesso_required
def excluir_gasto(request, token, pk):
    if request.method == 'POST':
        gasto = get_object_or_404(Gasto, pk=pk, cliente=request.cliente)
        gasto.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@acesso_required
def relatorios(request, token):
    return render(request, 'relatorios.html', {'token': token, 'cliente': request.cliente})


@acesso_required
def gerar_relatorio(request, token):
    cliente = request.cliente
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    try:
        dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Datas inválidas'}, status=400)

    insumos_qs = Insumo.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim])
    vendas_qs = Venda.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim]).select_related('insumo')
    gastos_qs = Gasto.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim])

    FORMAS = {'dinheiro': 'Dinheiro', 'pix': 'PIX', 'cartao_credito': 'Cartão Crédito',
              'cartao_debito': 'Cartão Débito', 'outro': 'Outro'}

    def fmt(dt): return dt.strftime('%d/%m/%Y %H:%M') if dt else ''

    return JsonResponse({
        'success': True,
        'resumo': {
            'total_insumos': sum(float(i.valor_total) for i in insumos_qs),
            'total_vendas': sum(float(v.valor_total) for v in vendas_qs),
            'total_gastos': sum(float(g.valor) for g in gastos_qs),
            'lucro': sum(float(v.valor_total) for v in vendas_qs) - sum(float(g.valor) for g in gastos_qs),
        },
        'insumos': [{'num': i+1, 'id': r.id, 'nome': r.nome, 'preco_custo': float(r.preco_custo),
            'preco': float(r.preco), 'quantidade': float(r.quantidade), 'unidade': r.unidade,
            'total': float(r.valor_total), 'data_hora': fmt(r.data_hora)} for i, r in enumerate(insumos_qs)],
        'vendas': [{'num': i+1, 'id': v.id, 'insumo': v.insumo.nome,
            'quantidade': float(v.quantidade_vendida), 'preco_venda': float(v.preco_venda),
            'desconto': float(v.desconto), 'total': float(v.valor_total),
            'forma_pagamento': FORMAS.get(v.forma_pagamento, v.forma_pagamento),
            'cliente': v.cliente_nome, 'data_hora': fmt(v.data_hora)} for i, v in enumerate(vendas_qs)],
        'gastos': [{'num': i+1, 'id': g.id, 'descricao': g.descricao, 'valor': float(g.valor),
            'categoria': g.categoria, 'data_hora': fmt(g.data_hora), 'observacao': g.observacao
            } for i, g in enumerate(gastos_qs)],
    })


@acesso_required
def exportar_csv(request, token):
    cliente = request.cliente
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    try:
        dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        return HttpResponse('Datas inválidas', status=400)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{data_inicio}_{data_fim}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)

    writer.writerow(['=== INSUMOS ==='])
    writer.writerow(['#', 'Nome', 'Custo', 'Preço Venda', 'Quantidade', 'Unidade', 'Total', 'Data/Hora'])
    for i, ins in enumerate(Insumo.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim]), 1):
        writer.writerow([i, ins.nome, ins.preco_custo, ins.preco, ins.quantidade, ins.unidade, ins.valor_total, ins.data_hora.strftime('%d/%m/%Y %H:%M')])

    writer.writerow([])
    writer.writerow(['=== VENDAS ==='])
    writer.writerow(['#', 'Insumo', 'Qtd', 'Preço', 'Desconto', 'Total', 'Pagamento', 'Cliente', 'Data/Hora'])
    for i, v in enumerate(Venda.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim]).select_related('insumo'), 1):
        writer.writerow([i, v.insumo.nome, v.quantidade_vendida, v.preco_venda, v.desconto, v.valor_total, v.get_forma_pagamento_display(), v.cliente_nome, v.data_hora.strftime('%d/%m/%Y %H:%M')])

    writer.writerow([])
    writer.writerow(['=== GASTOS ==='])
    writer.writerow(['#', 'Descrição', 'Valor', 'Categoria', 'Data/Hora'])
    for i, g in enumerate(Gasto.objects.filter(cliente=cliente, data_hora__range=[dt_inicio, dt_fim]), 1):
        writer.writerow([i, g.descricao, g.valor, g.get_categoria_display(), g.data_hora.strftime('%d/%m/%Y %H:%M')])

    return response


# ── ADMIN SIMPLES ─────────────────────────────────────────────────────────────

def admin_clientes(request):
    """Painel simples para você ver e gerenciar clientes"""
    senha = request.GET.get('senha', '')
    SENHA_ADMIN = os.environ.get('ADMIN_SENHA', 'admin123')
    if senha != SENHA_ADMIN:
        return HttpResponse('Acesso negado. Use ?senha=SUA_SENHA', status=403)
    clientes = Cliente.objects.prefetch_related('pagamentos').order_by('-criado_em')
    return render(request, 'admin_clientes.html', {'clientes': clientes})


def admin_aprovar(request, token):
    """Aprova manualmente um pagamento (fallback)"""
    senha = request.GET.get('senha', '')
    SENHA_ADMIN = os.environ.get('ADMIN_SENHA', 'admin123')
    if senha != SENHA_ADMIN:
        return HttpResponse('Acesso negado.', status=403)
    cliente = get_object_or_404(Cliente, token=token)
    cliente.ativo = True
    if cliente.acesso_ate and cliente.acesso_ate > timezone.now():
        cliente.acesso_ate += timedelta(days=30)
    else:
        cliente.acesso_ate = timezone.now() + timedelta(days=30)
    cliente.save()
    return JsonResponse({'success': True, 'acesso_ate': str(cliente.acesso_ate)})

