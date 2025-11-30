# Trabalho de Infraestrutura de Comunicação — 2025.2

Este projeto implementa, em **Python**, um sistema de envio confiável de mensagens na camada de aplicação, utilizando **sockets TCP** e simulando o comportamento dos protocolos **Go-Back-N (GBN)** e **Selective Repeat** (SR) em presença de erros e perdas.

O sistema é composto de:

* Cliente → envia mensagem segmentada, controla janela, timeouts e retransmissões

* Servidor → valida pacotes, confirma via ACK/NAK e reconstrói a mensagem

## Objetivo

1. Simular mecanismos da camada de transporte:

2. Numeração de pacotes

3. Janela deslizante

4. ACK/NAK

5. Retransmissão

6. Checksum manual

7. Simulação determinística de erros e perdas

8. Entrada e saída de dados via protocolo definido pelo grupo

## ⚙️ Arquitetura Geral
CLIENTE ---- `(socket TCP) ----> SERVIDOR`


O transporte real é TCP, mas todo o comportamento confiável é simulado na aplicação, conforme exigido no trabalho.

## Handshake

Assim que o cliente conecta ao servidor, envia:

```
protocolo,modo_erro,packet_size,crypto_flag
```

O servidor responde:

```
HANDSHAKE_OK:<GBN|SR>:<window_size>
```

A janela é definida exclusivamente pelo servidor (valor inicial = 5)

O cliente apenas aceita o valor informado

## 📦 Formato dos Pacotes

Cada pacote enviado possui o formato:

```
<seq> - S - <payload> - <checksum>
```

Onde:

- seq: número de sequência (2 dígitos, iniciando em 01)

- S: flag fixa (envio normal)

- payload: trecho de até 3 caracteres (≤ 4 conforme regras do projeto)

- checksum: soma manual (determinística)

## Checksum Manual

Implementado conforme solicitado:

```
def calcular_checksum_manual(dados):
    soma = 0
    for i, c in enumerate(dados):
        soma += (i + 1) * ord(c)
    return hex(soma)[2:].zfill(8)[:8]
```

O servidor recalcula e compara.

## Janela Deslizante

- Definida EXCLUSIVAMENTE pelo servidor

- Valor inicial = 5

- Varia logicamente de 1 a 5 pacotes pendentes

- Cliente usa:

    - GBN → ACK cumulativo

    - SR → ACK individual, janela avançando conforme send_base

## 🔁 Protocolos Implementados

### 1. Go-Back-N (GBN)

- Envia até window_size pacotes sem esperar

- ACK cumulativo

- Em erro/perda → retransmite a partir do send_base

### 2. Selective Repeat (SR)

- Envio paralelo com timers independentes

- ACK individual por sequência

- Buffer no servidor

- Retransmissão apenas dos pacotes faltantes

## Simulação Determinística de Falhas

Configurada no cliente:

- Modo 2 – Perda: usuário escolhe quais pacotes serão perdidos, exatamente 1 vez

- Modo 3 – Erro: usuário escolhe quais pacotes serão corrompidos

Nada de random → tudo 100% determinístico (como o monitor pediu).

## 🔐 Criptografia (extra)

Implementada criptografia XOR opcional:

- Cliente cifra payload

- Servidor decifra antes de validar checksum

## ▶ 10. Como Executar
Servidor
```
python servidor.py
```

Saída esperada:
```
[SERVER] Aguardando conexões em 127.0.0.1:5001...
[SERVER] Protocolo=GBN, Modo=Seguro, PacketMax=3, Janela=5
```
Cliente
```
python cliente.py
```

Fluxo:

1. Escolha do protocolo (GBN ou SR)

2. Escolha do modo de erro

3. Timeout

4. Mensagem (≥ 30 caracteres)

5. Execução automática com envio e ACK/NAK

## 📄 Exemplo de Execução (GBN)

Cliente:

```
[CLIENT] Handshake: HANDSHAKE_OK:GBN:5
[CLIENT] Janela configurada = 5
[CLIENT] Enviado: 01 -
[CLIENT] Enviado: 02 -
[CLIENT] Recebeu ACK 01
[CLIENT] Recebeu NAK 02
[CLIENT] Timeout GBN, retransmitindo a partir de 02
```

Servidor:

```
[SERVER] Recebido pacote 01
[SERVER] Frame inválido: 02 ...
[SERVER] Enviando NAK02
[SERVER] Recebido pacote 02
``` 

## 📄 Exemplo de Execução (SR)

Cliente:

```
[CLIENT] Handshake: HANDSHAKE_OK:SR:5
[CLIENT] Enviado: 01
[CLIENT] Enviado: 02
[CLIENT] Recebeu ACK 02
[CLIENT] Enviado: 03
```

Servidor:

```
[SERVER] Recebido pacote 02
[SERVER] Recebido pacote 01
[SERVER] ACK02 ACK01
```

## Encerramento da Comunicação

Cliente envia `"FIM"` → servidor envia `"FIM_ACK"` → ambos encerram conexões.