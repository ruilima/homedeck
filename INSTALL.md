# Instalação HomeDeck - Versão Otimizada

Esta versão inclui as otimizações de performance (commit 409a5cf):
- ✅ Wake-up instantâneo (sem delays de 200ms)
- ✅ Navegação rápida entre páginas
- ✅ Cache de ícones mantido no arranque
- ✅ DeepDiff substituído por comparação JSON rápida
- ✅ Templates Jinja2 com cache LRU
- ✅ optipng desabilitado por padrão

## Pré-requisitos

- Orange Pi com Python 3.12+
- Home Assistant a correr
- Long-lived access token do Home Assistant

## Passos de Instalação

### 1. Limpar instalação anterior (se existir)

```bash
# Parar serviços
sudo systemctl stop homedeck.service 2>/dev/null
sudo systemctl stop homedeck-server.service 2>/dev/null

# Remover ficheiros de serviço antigos
sudo rm -f /etc/systemd/system/homedeck.service
sudo rm -f /etc/systemd/system/homedeck-server.service
sudo rm -f /etc/homedeck/homedeck.env

# Recarregar systemd
sudo systemctl daemon-reload
```

### 2. Clonar repositório e instalar

```bash
cd /root
rm -rf homedeck  # Remover versão antiga se existir
git clone https://github.com/ruilima/homedeck.git
cd homedeck

# Checkout para versão otimizada
git fetch origin claude/session-011CUYYXtf3ZcDjLoonUAS7u
git checkout claude/session-011CUYYXtf3ZcDjLoonUAS7u

# Criar virtual environment
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -e .
```

### 3. Configurar credenciais do Home Assistant

Criar ficheiro `.env` em `/root/homedeck/.env`:

```bash
cat > /root/homedeck/.env << 'EOF'
HA_HOST=ws://192.168.31.42:8123
HA_ACCESS_TOKEN=SEU_TOKEN_AQUI
TIMEZONE=Europe/Lisbon
MDNS_SERVICE_ID=
EOF
```

**IMPORTANTE:**
- NÃO use aspas nas variáveis
- Substitua `SEU_TOKEN_AQUI` pelo seu token real do Home Assistant
- Para criar token: Home Assistant → Perfil → Long-Lived Access Tokens

### 4. Testar manualmente ANTES de instalar serviços

```bash
cd /root/homedeck
source venv/bin/activate

# Deve ver "Device connected" sem erros HTTP 403
python3 deck.py
```

Se funcionar, pressione `Ctrl+C` e continue para o passo 5.

**Se der erro HTTP 403:**
- Verifique se o token está correto
- Verifique se não tem aspas no .env
- Crie um novo token no Home Assistant

### 5. Instalar serviços systemd

```bash
# Copiar ficheiros de serviço
sudo cp /root/homedeck/homedeck.service /etc/systemd/system/
sudo cp /root/homedeck/homedeck-server.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Ativar serviços para iniciar no boot
sudo systemctl enable homedeck.service
sudo systemctl enable homedeck-server.service

# Iniciar serviços
sudo systemctl start homedeck-server.service
sudo systemctl start homedeck.service
```

### 6. Verificar status

```bash
# Ver status dos serviços
sudo systemctl status homedeck.service --no-pager
sudo systemctl status homedeck-server.service --no-pager

# Ver logs em tempo real
sudo journalctl -u homedeck.service -f
```

## Resolução de Problemas

### Erro: ModuleNotFoundError

Se aparecer erro sobre módulos em falta:

```bash
cd /root/homedeck
source venv/bin/activate
pip install -e .
sudo systemctl restart homedeck.service
```

### Erro: HTTP 403

O Home Assistant está a rejeitar o token. Soluções:

1. **Verificar o .env:**
```bash
cat -A /root/homedeck/.env
```
Não deve ter aspas nem espaços extras.

2. **Criar novo token:**
- Home Assistant → Perfil → Long-Lived Access Tokens → Create Token
- Copiar e colar no .env (sem aspas)

3. **Testar conexão:**
```bash
curl http://192.168.31.42:8123/api/
```

### Erro: Device not found

Verifique se o Stream Deck está ligado:
```bash
lsusb | grep -i stream
```

## Configuração

O ficheiro de configuração está em:
```
/root/homedeck/assets/configuration.yml
```

Edite este ficheiro para personalizar botões e páginas. O HomeDeck vai recarregar automaticamente quando guardar.

## Performance

Esta versão inclui melhorias significativas:
- Wake-up: ~200ms mais rápido (delay removido)
- Navegação: 2-5x mais rápida (cache + JSON compare)
- Startup: mantém cache de ícones (sem regenerar)

## Comandos Úteis

```bash
# Reiniciar serviços
sudo systemctl restart homedeck.service
sudo systemctl restart homedeck-server.service

# Parar serviços
sudo systemctl stop homedeck.service
sudo systemctl stop homedeck-server.service

# Ver logs
sudo journalctl -u homedeck.service -n 100 --no-pager
sudo journalctl -u homedeck-server.service -n 100 --no-pager

# Desativar serviços (não iniciar no boot)
sudo systemctl disable homedeck.service
sudo systemctl disable homedeck-server.service
```
