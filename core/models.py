from django.db import models
from django.utils import timezone


class Insumo(models.Model):
    nome = models.CharField(max_length=200)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=50, default='un')
    data_hora = models.DateTimeField(default=timezone.now)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Insumo'
        verbose_name_plural = 'Insumos'

    def __str__(self):
        return self.nome

    @property
    def valor_total(self):
        return self.preco * self.quantidade


class Venda(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='vendas')
    quantidade_vendida = models.DecimalField(max_digits=10, decimal_places=2)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    cliente = models.CharField(max_length=200, blank=True, default='')
    data_hora = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'

    def __str__(self):
        return f"Venda {self.id} - {self.insumo.nome}"

    @property
    def valor_total(self):
        return self.preco_venda * self.quantidade_vendida


class Gasto(models.Model):
    CATEGORIAS = [
        ('operacional', 'Operacional'),
        ('material', 'Material'),
        ('servico', 'Serviço'),
        ('pessoal', 'Pessoal'),
        ('outro', 'Outro'),
    ]
    descricao = models.CharField(max_length=300)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='outro')
    data_hora = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor}"