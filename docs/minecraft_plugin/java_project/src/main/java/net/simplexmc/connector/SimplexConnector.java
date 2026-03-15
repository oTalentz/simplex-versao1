package net.simplexmc.connector;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Random;
import java.util.logging.Level;

public class SimplexConnector extends JavaPlugin {

    private String apiUrl;
    private String agentName;
    private String authToken;
    private boolean isPairing = false;
    private String pairingCode = "";
    private final Gson gson = new Gson();

    @Override
    public void onEnable() {
        saveDefaultConfig();
        loadConfigValues();

        getLogger().info("SimplexConnector iniciado. API: " + apiUrl);

        if (authToken == null || authToken.isEmpty()) {
            getLogger().info("Token não encontrado. Iniciando modo de pareamento...");
            startPairing();
        } else {
            getLogger().info("Token encontrado. Conectado como " + agentName);
            startMainLoop();
        }
    }

    @Override
    public void onDisable() {
        getLogger().info("SimplexConnector desativado.");
    }

    private void loadConfigValues() {
        apiUrl = getConfig().getString("api_url", "https://www.simplexmc.net/api");
        agentName = getConfig().getString("agent_name", "mc-server-01");
        authToken = getConfig().getString("auth_token", "");
    }

    private void startPairing() {
        isPairing = true;
        pairingCode = generateCode();

        // Register code in backend
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    JsonObject json = new JsonObject();
                    json.addProperty("code", pairingCode);
                    json.addProperty("agent", agentName);

                    String response = sendRequest("POST", "/connector/setup/init", json.toString());
                    
                } catch (Exception e) {
                    getLogger().log(Level.SEVERE, "Erro ao registrar código de pareamento: " + e.getMessage());
                }
            }
        }.runTaskAsynchronously(this);

        // Reminder Task - Flashy message every 15s
        new BukkitRunnable() {
            @Override
            public void run() {
                if (!isPairing || (authToken != null && !authToken.isEmpty())) {
                    this.cancel();
                    return;
                }
                printPairingMessage();
            }
        }.runTaskTimer(this, 0L, 300L); // 0 delay, 300 ticks = 15 seconds

        // Polling task
        new BukkitRunnable() {
            @Override
            public void run() {
                if (!isPairing || (authToken != null && !authToken.isEmpty())) {
                    this.cancel();
                    return;
                }

                try {
                    String response = sendRequest("GET", "/connector/setup/poll?code=" + pairingCode, null);
                    if (response != null) {
                        JsonObject json = JsonParser.parseString(response).getAsJsonObject();
                        if (json.has("status")) {
                            String status = json.get("status").getAsString();
                            if ("CLAIMED".equals(status)) {
                                authToken = json.get("token").getAsString();
                                
                                // Save to config
                                getConfig().set("auth_token", authToken);
                                saveConfig();
                                
                                isPairing = false;
                                getLogger().info("=========================================");
                                getLogger().info("PAREAMENTO CONCLUÍDO!");
                                getLogger().info("Token salvo com sucesso.");
                                getLogger().info("=========================================");
                                
                                new BukkitRunnable() {
                                    @Override
                                    public void run() {
                                        startMainLoop();
                                    }
                                }.runTask(SimplexConnector.this);
                                
                                this.cancel();
                            } else if ("EXPIRED".equals(status)) {
                                getLogger().info("Código expirado. Gerando novo...");
                                startPairing(); // Restart process
                                this.cancel();
                            }
                        }
                    }
                } catch (Exception e) {
                    // Silent fail for polling to avoid spam
                }
            }
        }.runTaskTimerAsynchronously(this, 100L, 100L); // Every 5 seconds
    }

    private void printPairingMessage() {
        ConsoleCommandSender sender = Bukkit.getConsoleSender();
        sender.sendMessage(ChatColor.GOLD + "=========================================");
        sender.sendMessage(ChatColor.RED + "" + ChatColor.BOLD + "       SIMPLEX: PAREAMENTO NECESSÁRIO");
        sender.sendMessage("");
        sender.sendMessage(ChatColor.YELLOW + "   Código de Vinculação: " + ChatColor.AQUA + ChatColor.BOLD + pairingCode);
        sender.sendMessage("");
        sender.sendMessage(ChatColor.YELLOW + "   Insira este código no Painel Admin");
        sender.sendMessage(ChatColor.YELLOW + "   Acesse: " + ChatColor.UNDERLINE + "Configurações > Conectar Servidor");
        sender.sendMessage(ChatColor.GOLD + "=========================================");
    }

    private void startMainLoop() {
        int interval = getConfig().getInt("check_interval", 15) * 20; // Convert to ticks

        new BukkitRunnable() {
            @Override
            public void run() {
                if (authToken == null || authToken.isEmpty()) return;

                try {
                    // 1. Heartbeat
                    JsonObject hb = new JsonObject();
                    hb.addProperty("type", "heartbeat");
                    JsonObject payload = new JsonObject();
                    payload.addProperty("agent", agentName);
                    payload.addProperty("online", Bukkit.getOnlinePlayers().size());
                    hb.add("payload", payload);

                    sendRequest("POST", "/connector/events", hb.toString());

                    // 2. Check Deliveries
                    String deliveryRes = sendRequest("GET", "/connector/deliveries", null);
                    if (deliveryRes != null && !deliveryRes.isEmpty()) {
                        JsonElement element = JsonParser.parseString(deliveryRes);
                        if (element.isJsonArray()) {
                            JsonArray deliveries = element.getAsJsonArray();
                            for (JsonElement d : deliveries) {
                                processDelivery(d.getAsJsonObject());
                            }
                        }
                    }

                } catch (Exception e) {
                    getLogger().warning("Erro no loop principal: " + e.getMessage());
                }
            }
        }.runTaskTimerAsynchronously(this, 0L, interval);
    }

    private void processDelivery(JsonObject delivery) {
        String id = delivery.get("id").getAsString();
        String customerName = delivery.get("customer_name").getAsString();
        String product = delivery.get("product").getAsString();

        getLogger().info("Processando entrega: " + product + " para " + customerName + " (ID: " + id + ")");

        String commandTemplate = getConfig().getString("products." + product);
        if (commandTemplate != null) {
            String finalCommand = commandTemplate.replace("%player%", customerName);
            
            // Execute command on main thread
            new BukkitRunnable() {
                @Override
                public void run() {
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(), finalCommand);
                }
            }.runTask(this);
            
            // Confirm delivery
            confirmDelivery(id);
        } else {
            getLogger().warning("Produto desconhecido: " + product);
        }
    }

    private void confirmDelivery(String id) {
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    JsonObject json = new JsonObject();
                    json.addProperty("id", id);
                    sendRequest("POST", "/connector/deliveries/confirm", json.toString());
                    getLogger().info("Entrega confirmada para ID " + id);
                } catch (Exception e) {
                    getLogger().warning("Erro ao confirmar entrega " + id + ": " + e.getMessage());
                }
            }
        }.runTaskAsynchronously(this);
    }

    private String generateCode() {
        String chars = "ABCDEF0123456789";
        StringBuilder sb = new StringBuilder();
        Random random = new Random();
        for (int i = 0; i < 6; i++) {
            sb.append(chars.charAt(random.nextInt(chars.length())));
        }
        return sb.toString();
    }

    private String sendRequest(String method, String endpoint, String body) throws Exception {
        URL url = new URL(apiUrl + endpoint);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("User-Agent", "SimplexConnector/1.0");
        
        if (authToken != null && !authToken.isEmpty()) {
            conn.setRequestProperty("Authorization", "Bearer " + authToken);
        }

        conn.setDoOutput(true);
        
        if (body != null && !body.isEmpty()) {
            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = body.getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }
        }

        int responseCode = conn.getResponseCode();
        if (responseCode >= 200 && responseCode < 300) {
            try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                StringBuilder response = new StringBuilder();
                String responseLine;
                while ((responseLine = br.readLine()) != null) {
                    response.append(responseLine.trim());
                }
                return response.toString();
            }
        } else {
            if (responseCode == 401) {
                getLogger().warning("Token inválido ou expirado. Reinicie o pareamento.");
                // Optionally clear token here
            }
            return null;
        }
    }
    
    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (command.getName().equalsIgnoreCase("simplex")) {
            if (args.length > 0) {
                if (args[0].equalsIgnoreCase("reload")) {
                    reloadConfig();
                    loadConfigValues();
                    sender.sendMessage(ChatColor.GREEN + "[Simplex] Configuração recarregada.");
                    return true;
                } else if (args[0].equalsIgnoreCase("setup")) {
                    if (!(sender instanceof ConsoleCommandSender)) {
                        sender.sendMessage(ChatColor.RED + "Este comando só pode ser executado via console.");
                        return true;
                    }
                    authToken = "";
                    getConfig().set("auth_token", "");
                    saveConfig();
                    startPairing();
                    sender.sendMessage(ChatColor.YELLOW + "[Simplex] Pareamento reiniciado. Verifique o console.");
                    return true;
                }
            }
        }
        return false;
    }
}
