# Guia de Configuração da Entrega Automática

Para que o seu servidor Minecraft receba as entregas de VIPs automaticamente, você **NÃO** precisa configurar as variáveis `VIP_DELIVERY_BRIDGE` na Vercel. O sistema utiliza um método moderno onde o servidor se conecta ao site.

Siga estes passos:

## 1. Localize o Plugin
No diretório do seu projeto, localize o arquivo do plugin já compilado:
`docs/minecraft_plugin/java_project/target/simplex-connector-1.0.jar`

## 2. Instale no Servidor
1.  Pare o seu servidor Minecraft.
2.  Copie o arquivo `simplex-connector-1.0.jar` para a pasta `plugins/` do seu servidor.
3.  Inicie o servidor Minecraft.

## 3. Configure o Plugin
1.  Após iniciar, o plugin vai gerar uma pasta `plugins/SimplexConnector/`.
2.  Abra o arquivo `config.yml` dentro dessa pasta.
3.  Altere a linha `api_url` para apontar para o seu site na Vercel:
    ```yaml
    api_url: "https://seu-projeto-na-vercel.app/api"
    agent_name: "servidor-principal"
    ```
4.  Salve o arquivo e reinicie o servidor (ou use `/reload` se suportado, mas reiniciar é melhor).

## 4. Pareamento (Conectar ao Site)
1.  No console do servidor Minecraft, você verá uma mensagem amarela com um código de pareamento, por exemplo:
    `[SimplexConnector] Use este código no painel: X7K9-M2P1`
2.  Acesse o painel administrativo do seu site (`/painel`).
3.  Vá em **Configurações** -> **Conectar Servidor**.
4.  Digite o código exibido no console.

## 5. Pronto!
O servidor agora está conectado.
- O site enviará os comandos de VIP automaticamente para o servidor.
- Você pode ver o status "Online" no painel.
- As variáveis `VIP_DELIVERY_BRIDGE_URL` e `VIP_DELIVERY_BRIDGE_TOKEN` na Vercel podem ser removidas ou deixadas em branco.
