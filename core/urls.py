from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Insumos
    path('insumos/', views.insumos, name='insumos'),
    path('insumos/cadastrar/', views.cadastrar_insumo, name='cadastrar_insumo'),
    path('insumos/<int:pk>/excluir/', views.excluir_insumo, name='excluir_insumo'),

    # Vendas
    path('vendas/', views.vendas, name='vendas'),
    path('vendas/cadastrar/', views.cadastrar_venda, name='cadastrar_venda'),
    path('vendas/insumo/<int:pk>/preco/', views.get_insumo_preco, name='get_insumo_preco'),

    # Gastos
    path('gastos/', views.gastos, name='gastos'),
    path('gastos/cadastrar/', views.cadastrar_gasto, name='cadastrar_gasto'),
    path('gastos/<int:pk>/excluir/', views.excluir_gasto, name='excluir_gasto'),

    # Relatórios
    path('relatorios/', views.relatorios, name='relatorios'),
    path('relatorios/gerar/', views.gerar_relatorio, name='gerar_relatorio'),
    path('relatorios/exportar-csv/', views.exportar_csv, name='exportar_csv'),
]