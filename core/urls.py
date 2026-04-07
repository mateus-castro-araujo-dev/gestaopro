from django.urls import path
from . import views

urlpatterns = [
    # Pública
    path('', views.landing, name='landing'),
    path('registrar/', views.registrar, name='registrar'),
    path('verificar/<str:token>/', views.verificar_pagamento, name='verificar_pagamento'),
    path('webhook/mercadopago/', views.webhook_mercadopago, name='webhook_mp'),
    # Sistema (com token)
    path('acesso/<str:token>/', views.home, name='home'),
    path('acesso/<str:token>/renovar/', views.renovar, name='renovar'),
    path('acesso/<str:token>/insumos/', views.insumos, name='insumos'),
    path('acesso/<str:token>/insumos/cadastrar/', views.cadastrar_insumo, name='cadastrar_insumo'),
    path('acesso/<str:token>/insumos/<int:pk>/excluir/', views.excluir_insumo, name='excluir_insumo'),
    path('acesso/<str:token>/vendas/', views.vendas, name='vendas'),
    path('acesso/<str:token>/vendas/cadastrar/', views.cadastrar_venda, name='cadastrar_venda'),
    path('acesso/<str:token>/vendas/<int:pk>/excluir/', views.excluir_venda, name='excluir_venda'),
    path('acesso/<str:token>/gastos/', views.gastos, name='gastos'),
    path('acesso/<str:token>/gastos/cadastrar/', views.cadastrar_gasto, name='cadastrar_gasto'),
    path('acesso/<str:token>/gastos/<int:pk>/excluir/', views.excluir_gasto, name='excluir_gasto'),
    path('acesso/<str:token>/relatorios/', views.relatorios, name='relatorios'),
    path('acesso/<str:token>/relatorios/gerar/', views.gerar_relatorio, name='gerar_relatorio'),
    path('acesso/<str:token>/relatorios/exportar-csv/', views.exportar_csv, name='exportar_csv'),

    # Admin
    path('painel-admin/', views.admin_clientes, name='admin_clientes'),
    path('painel-admin/aprovar/<str:token>/', views.admin_aprovar, name='admin_aprovar'),
]