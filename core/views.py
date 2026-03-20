from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST
from django.contrib import messages
import json
from decimal import Decimal
from datetime import datetime, date
import csv

from .models import Insumo, Venda, Gasto


# ─── HOME ───────────────────────────────────────────────────────────────────

def home(request):
    hoje = date.today()
    vendas_hoje = Venda.objects.filter(data_hora__date=hoje).aggregate(
        total=Sum('preco_venda'))['total'] or 0
    gastos_hoje = Gasto.objects.filter(data_hora__date=hoje).aggregate(
        total=Sum('valor'))['total'] or 0
    insumos_count = Insumo.objects.filter(ativo=True).count()
    vendas_count = Venda.objects.filter(data_hora__date=hoje).count()

    context = {
        'vendas_hoje': vendas_hoje,
        'gastos_hoje': gastos_hoje,
        'insumos_count': insumos_count,
        'vendas_count': vendas_count,
    }
    return render(request, 'home.html', context)


# ─── INSUMOS ────────────────────────────────────────────────────────────────

def insumos(request):
    lista = Insumo.objects.filter(ativo=True)
    return render(request, 'insumos.html', {'insumos': lista})


def cadastrar_insumo(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            insumo = Insumo.objects.create(
                nome=data['nome'],
                preco=Decimal(str(data['preco'])),
                quantidade=Decimal(str(data['quantidade'])),
                unidade=data.get('unidade', 'un'),
            )
            return JsonResponse({
                'success': True,
                'insumo': {
                    'id': insumo.id,
                    'nome': insumo.nome,
                    'preco': float(insumo.preco),
                    'quantidade': float(insumo.quantidade),
                    'unidade': insumo.unidade,
                    'data_hora': insumo.data_hora.strftime('%d/%m/%Y %H:%M'),
                    'valor_total': float(insumo.valor_total),
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


def excluir_insumo(request, pk):
    if request.method == 'POST':
        insumo = get_object_or_404(Insumo, pk=pk)
        insumo.ativo = False
        insumo.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


# ─── VENDAS ─────────────────────────────────────────────────────────────────

def vendas(request):
    lista = Venda.objects.select_related('insumo').all()
    insumos_disponiveis = Insumo.objects.filter(ativo=True, quantidade__gt=0)
    return render(request, 'vendas.html', {
        'vendas': lista,
        'insumos': insumos_disponiveis,
    })


def cadastrar_venda(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            insumo = get_object_or_404(Insumo, pk=data['insumo_id'], ativo=True)

            qtd = Decimal(str(data['quantidade']))
            if qtd > insumo.quantidade:
                return JsonResponse({
                    'success': False,
                    'error': f'Quantidade insuficiente. Disponível: {insumo.quantidade} {insumo.unidade}'
                }, status=400)

            venda = Venda.objects.create(
                insumo=insumo,
                quantidade_vendida=qtd,
                preco_venda=Decimal(str(data['preco_venda'])),
                cliente=data.get('cliente', ''),
                observacao=data.get('observacao', ''),
            )

            insumo.quantidade -= qtd
            insumo.save()

            return JsonResponse({
                'success': True,
                'venda': {
                    'id': venda.id,
                    'insumo': insumo.nome,
                    'quantidade': float(venda.quantidade_vendida),
                    'preco_venda': float(venda.preco_venda),
                    'cliente': venda.cliente,
                    'data_hora': venda.data_hora.strftime('%d/%m/%Y %H:%M'),
                    'valor_total': float(venda.valor_total),
                    'estoque_restante': float(insumo.quantidade),
                    'unidade': insumo.unidade,
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


def get_insumo_preco(request, pk):
    insumo = get_object_or_404(Insumo, pk=pk)
    return JsonResponse({
        'preco': float(insumo.preco),
        'quantidade': float(insumo.quantidade),
        'unidade': insumo.unidade,
    })


# ─── GASTOS ─────────────────────────────────────────────────────────────────

def gastos(request):
    lista = Gasto.objects.all()
    return render(request, 'gastos.html', {'gastos': lista})


def cadastrar_gasto(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            gasto = Gasto.objects.create(
                descricao=data['descricao'],
                valor=Decimal(str(data['valor'])),
                categoria=data.get('categoria', 'outro'),
                observacao=data.get('observacao', ''),
            )
            return JsonResponse({
                'success': True,
                'gasto': {
                    'id': gasto.id,
                    'descricao': gasto.descricao,
                    'valor': float(gasto.valor),
                    'categoria': gasto.get_categoria_display(),
                    'categoria_raw': gasto.categoria,
                    'data_hora': gasto.data_hora.strftime('%d/%m/%Y %H:%M'),
                    'observacao': gasto.observacao,
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


def excluir_gasto(request, pk):
    if request.method == 'POST':
        gasto = get_object_or_404(Gasto, pk=pk)
        gasto.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


# ─── RELATÓRIOS ─────────────────────────────────────────────────────────────

def relatorios(request):
    return render(request, 'relatorios.html')


def gerar_relatorio(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Datas inválidas'}, status=400)

    insumos = Insumo.objects.filter(data_hora__range=[dt_inicio, dt_fim]).values(
        'id', 'nome', 'preco', 'quantidade', 'unidade', 'data_hora'
    )
    vendas = Venda.objects.filter(data_hora__range=[dt_inicio, dt_fim]).select_related('insumo').values(
        'id', 'insumo__nome', 'quantidade_vendida', 'preco_venda', 'cliente', 'data_hora', 'observacao'
    )
    gastos_qs = Gasto.objects.filter(data_hora__range=[dt_inicio, dt_fim]).values(
        'id', 'descricao', 'valor', 'categoria', 'data_hora', 'observacao'
    )

    total_insumos = sum(float(i['preco']) * float(i['quantidade']) for i in insumos)
    total_vendas = sum(float(v['quantidade_vendida']) * float(v['preco_venda']) for v in vendas)
    total_gastos = sum(float(g['valor']) for g in gastos_qs)

    def fmt_dt(dt):
        if dt:
            return dt.strftime('%d/%m/%Y %H:%M')
        return ''

    return JsonResponse({
        'success': True,
        'resumo': {
            'total_insumos': total_insumos,
            'total_vendas': total_vendas,
            'total_gastos': total_gastos,
            'lucro': total_vendas - total_gastos,
        },
        'insumos': [{
            'num': i + 1,
            'id': r['id'],
            'nome': r['nome'],
            'preco': float(r['preco']),
            'quantidade': float(r['quantidade']),
            'unidade': r['unidade'],
            'total': float(r['preco']) * float(r['quantidade']),
            'data_hora': fmt_dt(r['data_hora']),
        } for i, r in enumerate(insumos)],
        'vendas': [{
            'num': i + 1,
            'id': r['id'],
            'insumo': r['insumo__nome'],
            'quantidade': float(r['quantidade_vendida']),
            'preco_venda': float(r['preco_venda']),
            'total': float(r['quantidade_vendida']) * float(r['preco_venda']),
            'cliente': r['cliente'],
            'data_hora': fmt_dt(r['data_hora']),
        } for i, r in enumerate(vendas)],
        'gastos': [{
            'num': i + 1,
            'id': r['id'],
            'descricao': r['descricao'],
            'valor': float(r['valor']),
            'categoria': r['categoria'],
            'data_hora': fmt_dt(r['data_hora']),
            'observacao': r['observacao'],
        } for i, r in enumerate(gastos_qs)],
    })


def exportar_csv(request):
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
    writer.writerow(['#', 'Nome', 'Preço Unit.', 'Quantidade', 'Unidade', 'Total', 'Data/Hora'])
    for i, ins in enumerate(Insumo.objects.filter(data_hora__range=[dt_inicio, dt_fim]), 1):
        writer.writerow([i, ins.nome, ins.preco, ins.quantidade, ins.unidade,
                         ins.valor_total, ins.data_hora.strftime('%d/%m/%Y %H:%M')])

    writer.writerow([])
    writer.writerow(['=== VENDAS ==='])
    writer.writerow(['#', 'Insumo', 'Qtd Vendida', 'Preço Venda', 'Total', 'Cliente', 'Data/Hora'])
    for i, v in enumerate(Venda.objects.filter(data_hora__range=[dt_inicio, dt_fim]).select_related('insumo'), 1):
        writer.writerow([i, v.insumo.nome, v.quantidade_vendida, v.preco_venda,
                         v.valor_total, v.cliente, v.data_hora.strftime('%d/%m/%Y %H:%M')])

    writer.writerow([])
    writer.writerow(['=== GASTOS ==='])
    writer.writerow(['#', 'Descrição', 'Valor', 'Categoria', 'Data/Hora', 'Observação'])
    for i, g in enumerate(Gasto.objects.filter(data_hora__range=[dt_inicio, dt_fim]), 1):
        writer.writerow([i, g.descricao, g.valor, g.get_categoria_display(),
                         g.data_hora.strftime('%d/%m/%Y %H:%M'), g.observacao])

    return response