# Trabalho de Infraestrutura de Comunicação

# 🖥️ Cliente-Servidor (GBN e SR)

Aplicação cliente-servidor em **Python** que implementa um transporte confiável na camada de aplicação, simulando os protocolos **Go-Back-N (GBN)** e **Selective Repeat (SR)**.  
O projeto inclui **handshake**, envio de pacotes, **checksum** e confirmações **ACK/NAK**.

---

## ⚙️ Funcionalidades

- **Handshake** entre cliente e servidor (`SYN`, `SYN-ACK`, `ACK`)
- **Modo GBN:** confirma pacotes por **janela**
- **Modo SR:** confirma pacotes **individualmente**
- **Segmentação** em blocos de **4 caracteres**
- **Controle de sequência**, **checksum** e **janela de transmissão (5 pacotes)**
- **Validação de entradas** no cliente
