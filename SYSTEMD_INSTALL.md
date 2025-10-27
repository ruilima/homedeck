# Instalação do Serviço Systemd para HomeDeck

## Passo 1: Ajustar o caminho do Python

Primeiro, verifica qual é o caminho do Python no teu sistema:

```bash
which python3
```

Se o resultado for diferente de `/usr/bin/python3`, edita os ficheiros `homedeck.service` e `homedeck-server.service` e ajusta a linha `ExecStart` com o caminho correto.

## Passo 2: Ajustar o caminho do projeto

Se o teu projeto não está em `/root/homedeck`, ajusta a linha `WorkingDirectory` e o caminho em `ExecStart` nos ficheiros de serviço.

## Passo 3: Copiar os ficheiros de serviço

```bash
cd /root/homedeck  # ou o caminho do teu projeto

# Copiar ficheiro de serviço principal (deck controller)
sudo cp homedeck.service /etc/systemd/system/

# Opcional: copiar ficheiro do servidor web
sudo cp homedeck-server.service /etc/systemd/system/
```

## Passo 4: Ativar e iniciar os serviços

```bash
# Recarregar configuração do systemd
sudo systemctl daemon-reload

# Ativar serviço principal (inicia automaticamente no boot)
sudo systemctl enable homedeck.service

# Iniciar serviço principal
sudo systemctl start homedeck.service

# Verificar status
sudo systemctl status homedeck.service

# Ver logs em tempo real
sudo journalctl -u homedeck.service -f
```

## Passo 5 (Opcional): Ativar servidor web

Se quiseres usar o servidor web:

```bash
sudo systemctl enable homedeck-server.service
sudo systemctl start homedeck-server.service
sudo systemctl status homedeck-server.service
```

## Comandos Úteis

```bash
# Ver logs
sudo journalctl -u homedeck.service -n 100

# Reiniciar serviço
sudo systemctl restart homedeck.service

# Parar serviço
sudo systemctl stop homedeck.service

# Desativar (não inicia no boot)
sudo systemctl disable homedeck.service

# Ver status
sudo systemctl status homedeck.service
```

## Resolução de Problemas

### Erro: "Failed to execute command: Exec format error"
Verifica se o Python está instalado:
```bash
python3 --version
```

### Erro: "No such file or directory"
Verifica se os caminhos em `WorkingDirectory` e `ExecStart` estão corretos.

### Serviço não inicia
Verifica os logs:
```bash
sudo journalctl -u homedeck.service -n 50 --no-pager
```

### Testar manualmente
Antes de usar o serviço, testa se funciona manualmente:
```bash
cd /root/homedeck
python3 deck.py
```

## Usando Virtual Environment (Opcional)

Se preferires usar um venv:

1. Cria o venv:
```bash
cd /root/homedeck
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

2. Edita `homedeck.service` e altera:
```ini
ExecStart=/root/homedeck/venv/bin/python3 /root/homedeck/deck.py
```

3. Recarrega e reinicia:
```bash
sudo systemctl daemon-reload
sudo systemctl restart homedeck.service
```

## Notas Importantes

- **Configuração**: Certifica-te que tens o `.env` e `assets/configuration.yml` configurados antes de iniciar o serviço
- **Permissões**: O serviço corre como `root` para ter acesso ao dispositivo USB (Stream Deck)
- **Logs**: Todos os outputs vão para o journald - usa `journalctl` para ver
- **Auto-restart**: O serviço reinicia automaticamente se crashar (aguarda 10 segundos)
