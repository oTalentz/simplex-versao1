# Guia de Instalação e Configuração - Simplex Delivery

Este guia explica como configurar o seu servidor de Minecraft para receber as entregas automáticas de VIPs do site.

## Pré-requisitos do Servidor

Certifique-se de que seu servidor (Spigot/Paper/Purpur) possui os seguintes plugins instalados:

1.  **Skript** (Versão recente compatível com sua versão do servidor)
2.  **Reqn** (Addon para requisições HTTP)
    *   Download: https://github.com/SovdeEth/Reqn/releases
    *   *Nota: Se não conseguir usar o Reqn, addons como SkQuery ou Skript-Reflect também podem servir, mas o código atual foi feito pensando na sintaxe do Reqn.*

## Instalação do Script

1.  Navegue até a pasta `plugins/Skript/scripts/` no seu servidor.
2.  Crie um novo arquivo chamado `simplex_connector.sk`.
3.  Copie o conteúdo do arquivo `docs/minecraft_plugin/simplex_connector.sk` deste projeto e cole dentro do arquivo criado no servidor.
4.  Edite as opções no topo do arquivo se necessário:

```skript
options:
    simplex_api: https://simplexmc.net/api  <-- Mantenha assim para produção
    simplex_user: admin
    simplex_pass: admin123                  <-- Deve ser igual ao configurado no site
    simplex_agent: mc-server-01             <-- Nome identificador deste servidor
    
    # Comandos de entrega (personalize conforme seu plugin de permissão)
    cmd_lord: lp user %player% parent set lord
    cmd_knight: lp user %player% parent set knight
    # ...
```

5.  No jogo ou console, execute: `/sk reload simplex_connector`

## Como Funciona

1.  **Polling:** A cada 30 segundos, o script verifica no site se há novas entregas pendentes.
2.  **Entrega:** Se houver, ele executa o comando configurado no console.
3.  **Confirmação:** Após executar o comando, ele avisa o site que a entrega foi feita, e o status do pedido muda para "Entregue".
4.  **Heartbeat:** O script envia um sinal de vida a cada 30 segundos, mantendo o status "Online" no painel admin.

## Solução de Problemas

- **Erro de Login:** Verifique se usuário e senha batem com o `.env` do site.
- **Não conecta:** Verifique se o servidor tem acesso à internet e consegue alcançar `https://simplexmc.net`.
- **Erro de Script:** Se aparecer erros de sintaxe ao recarregar, verifique se você tem o addon **Reqn** instalado corretamente.
