from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets
import string


def gerar_token():
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(32))


class Cliente(models.Model):
    token = models.CharField(max_length=64, unique=True, default=gerar_token)
    nome = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    cpf_pix = models.CharField(max_length=20, blank=True, default='')
    criado_em = models.DateTimeField(default=timezone.now)
    ativo = models.BooleanField(default=False)
    acesso_ate = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f"{self.nome or self.email or self.token[:8]}"

    @property
    def acesso_valido(self):
        if not self.ativo:
            return False
        if self.acesso_ate is None:
            return False
        return timezone.now() < self.acesso_ate

    @property
    def dias_restantes(self):
        if not self.acesso_ate:
            return 0
        delta = self.acesso_ate - timezone.now()
        return max(0, delta.days)


class Pagamento(models.Model):
    STATUS = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('cancelado', 'Cancelado'),
        ('expirado', 'Expirado'),
    ]

    # Alterado para null/blank para permitir migração inicial segura
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pagamentos', null=True, blank=True)
    mp_payment_id = models.CharField(max_length=100, blank=True, default='')
    mp_preference_id = models.CharField(max_length=200, blank=True, default='')
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=20.00)
    status = models.CharField(max_length=20, choices=STATUS, default='pendente')
    criado_em = models.DateTimeField(default=timezone.now)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    qr_code = models.TextField(blank=True, default='')
    qr_code_base64 = models.TextField(blank=True, default='')
    pix_copia_cola = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    def __str__(self):
        return f"Pagamento {self.id} - {self.cliente} - {self.status}"

    def aprovar(self):
        self.status = 'aprovado'
        self.aprovado_em = timezone.now()
        self.save()
        
        # Ativa/renova cliente por 30 dias
        cliente = self.cliente
        if cliente:
            cliente.ativo = True
            if cliente.acesso_ate and cliente.acesso_ate > timezone.now():
                cliente.acesso_ate += timedelta(days=30)
            else:
                cliente.acesso_ate = timezone.now() + timedelta(days=30)
            cliente.save()


# ── Modelos do sistema de gestão vinculados ao cliente ────────────────────────

class Insumo(models.Model):
    # Alterado para null/blank para evitar erro de integridade no migrate
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='insumos', null=True, blank=True)
    nome = models.CharField(max_length=200)
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=50, default='un')
    data_hora = models.DateTimeField(default=timezone.now)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['-data_hora']

    def __str__(self):
        return self.nome

    @property
    def valor_total(self):
        return self.preco * self.quantidade

    @property
    def margem(self):
        if self.preco_custo > 0:
            return ((self.preco - self.preco_custo) / self.preco_custo) * 100
        return None


class Venda(models.Model):
    FORMAS_PAGAMENTO = [
        ('dinheiro', 'Dinheiro'),
        ('pix', 'PIX'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('cartao_debito', 'Cartão de Débito'),
        ('outro', 'Outro'),
    ]
    # Alterado para null/blank para evitar erro de integridade no migrate
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='vendas', null=True, blank=True)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='vendas')
    quantidade_vendida = models.DecimalField(max_digits=10, decimal_places=2)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pagamento = models.CharField(max_length=20, choices=FORMAS_PAGAMENTO, default='dinheiro')
    cliente_nome = models.CharField(max_length=200, blank=True, default='')
    data_hora = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-data_hora']

    @property
    def valor_bruto(self):
        return self.preco_venda * self.quantidade_vendida

    @property
    def valor_total(self):
        return self.valor_bruto - self.desconto


class Gasto(models.Model):
    CATEGORIAS = [
        ('operacional', 'Operacional'),
        ('material', 'Material'),
        ('servico', 'Serviço'),
        ('pessoal', 'Pessoal'),
        ('outro', 'Outro'),
    ]
    # Alterado para null/blank para evitar erro de integridade no migrate
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='gastos', null=True, blank=True)
    descricao = models.CharField(max_length=300)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='outro')
    data_hora = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-data_hora']

    def __str__(self):
        return self.descricao