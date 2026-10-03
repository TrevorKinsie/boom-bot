package com.boombot.mmo;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.Executors;

/**
 * The HTTP front for the MMO: serves the browser client and the REST API used
 * to move, gather, bank, sell and move money into the shared wallet.
 *
 * <p>Built on the JDK's {@code com.sun.net.httpserver} so the service runs
 * with nothing but a JRE and the bundled SQLite driver.
 */
public final class HttpApi {
    private final World world;
    private final HttpServer server;

    public HttpApi(String bind, int port, World world) throws IOException {
        this.world = world;
        this.server = HttpServer.create(new InetSocketAddress(bind, port), 0);
        server.createContext("/", new RootHandler());
        server.setExecutor(Executors.newFixedThreadPool(8));
    }

    public void start() {
        server.start();
    }

    public void stop() {
        server.stop(0);
    }

    private final class RootHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange ex) throws IOException {
            String path = ex.getRequestURI().getPath();
            String method = ex.getRequestMethod();
            long started = System.currentTimeMillis();
            try {
                if ("OPTIONS".equals(method)) {
                    respond(ex, 204, null);
                    logRequest(ex, method, path, 204, started);
                    return;
                }
                if (path.equals("/") || path.startsWith("/static/")) {
                    serveStatic(ex, path);
                    logRequest(ex, method, path, 200, started);
                    return;
                }
                if (path.startsWith("/api/")) {
                    handleApi(ex, path, method);
                    logRequest(ex, method, path, 200, started);
                    return;
                }
                respondJson(ex, 404, Map.of("error", "Not found: " + path));
                logRequest(ex, method, path, 404, started);
            } catch (ApiException e) {
                respondJson(ex, e.status, Map.of("error", e.getMessage()));
                logRequest(ex, method, path, e.status, started);
            } catch (Exception e) {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("error", "Server error");
                body.put("detail", e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
                respondJson(ex, 500, body);
                logRequest(ex, method, path, 500, started);
                System.err.println("Request failed: " + method + " " + path + " -> " + e);
            }
        }

        private void logRequest(HttpExchange ex, String method, String path,
                                int status, long started) {
            long ms = System.currentTimeMillis() - started;
            System.out.println("[mmo] " + method + " " + path
                    + " -> " + status + " (" + ms + "ms)");
        }
    }

    // ------------------------------------------------------------------
    // Static client assets
    // ------------------------------------------------------------------

    private void serveStatic(HttpExchange ex, String path) throws IOException {
        String resource = "static/index.html";
        if (path.startsWith("/static/")) {
            resource = "static/" + path.substring("/static/".length());
        }
        if (resource.contains("..")) {
            respond(ex, 400, null);
            return;
        }
        InputStream in = HttpApi.class.getClassLoader().getResourceAsStream(resource);
        if (in == null) {
            respond(ex, 404, null);
            return;
        }
        byte[] data;
        try (in) {
            data = in.readAllBytes();
        }
        if ("GET".equals(ex.getRequestMethod())) {
            ex.getResponseHeaders().set("Content-Type", contentType(resource));
            ex.sendResponseHeaders(200, data.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(data);
            }
        } else {
            ex.sendResponseHeaders(200, -1);
            ex.close();
        }
    }

    private static String contentType(String resource) {
        if (resource.endsWith(".html")) return "text/html; charset=utf-8";
        if (resource.endsWith(".js")) return "application/javascript";
        if (resource.endsWith(".css")) return "text/css; charset=utf-8";
        if (resource.endsWith(".json")) return "application/json";
        if (resource.endsWith(".png")) return "image/png";
        if (resource.endsWith(".jpg") || resource.endsWith(".jpeg")) return "image/jpeg";
        if (resource.endsWith(".svg")) return "image/svg+xml";
        if (resource.endsWith(".woff2")) return "font/woff2";
        return "application/octet-stream";
    }

    // ------------------------------------------------------------------
    // Response helpers
    // ------------------------------------------------------------------

    private void respond(HttpExchange ex, int status, byte[] body) throws IOException {
        ex.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        byte[] data = body == null ? new byte[0] : body;
        ex.sendResponseHeaders(status, data.length);
        try (OutputStream os = ex.getResponseBody()) {
            if (data.length > 0) {
                os.write(data);
            }
        }
    }

    private void respondJson(HttpExchange ex, int status, Object obj) throws IOException {
        byte[] data = Json.write(obj).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        respond(ex, status, data);
    }

    private static String queryParam(HttpExchange ex, String key) {
        String q = ex.getRequestURI().getRawQuery();
        if (q == null) {
            return null;
        }
        for (String pair : q.split("&")) {
            int eq = pair.indexOf('=');
            if (eq > 0 && pair.substring(0, eq).equals(key)) {
                return pair.substring(eq + 1);
            }
        }
        return null;
    }

    private static Map<String, Object> readBody(HttpExchange ex) throws IOException {
        byte[] data = ex.getRequestBody().readAllBytes();
        if (data.length == 0) {
            return new LinkedHashMap<>();
        }
        return Util.asMap(Json.parse(new String(data, StandardCharsets.UTF_8)));
// ------------------------------------------------------------------
    // API routing
    // ------------------------------------------------------------------

}
    private void handleApi(HttpExchange ex, String path, String method) throws IOException {
        if ("POST".equals(method)) {
            handlePost(ex, path);
            return;
        }
        if ("GET".equals(method)) {
            handleGet(ex, path);
            return;
        }
        throw new ApiException(405, "Method not allowed: " + method);
    }

    private void handleGet(HttpExchange ex, String path) throws IOException {
        switch (path) {
            case "/api/world":
                respondJson(ex, 200, world.worldSnapshot());
                return;
            case "/api/game":
                respondJson(ex, 200, world.gameSnapshot(queryParam(ex, "token")));
                return;
            default:
                throw new ApiException(404, "Unknown endpoint: " + path);
        }
    }

    private void handlePost(HttpExchange ex, String path) throws IOException {
        Map<String, Object> body = readBody(ex);
        String token = str(body.get("token"));

        if ("/api/join".equals(path)) {
            Player p = world.joinOrResume(str(body.get("name")),
                    body.get("token") == null ? null : token);
            world.flushNow();
            respondJson(ex, 200, Map.of(
                    "ok", true,
                    "id", p.id,
                    "name", p.name,
                    "token", p.token));
            return;
        }

        Player player = requirePlayer(token);
        switch (path) {
            case "/api/move":
                world.move(player, Util.numDouble(body.get("x")), Util.numDouble(body.get("y")));
                break;
            case "/api/gather":
                world.gather(player, str(body.get("resourceId")));
                break;
            case "/api/stop":
                world.stop(player);
                break;
            case "/api/bank":
                world.bankItem(player, str(body.get("item")), Util.numLong(body.get("qty")));
                break;
            case "/api/withdraw_item":
                world.withdrawItem(player, str(body.get("item")), Util.numLong(body.get("qty")));
                break;
            case "/api/sell": {
                long coins = world.sell(player, str(body.get("item")), Util.numLong(body.get("qty")));
                world.flush();
                respondJson(ex, 200, Map.of(
                        "ok", true,
                        "coins", coins,
                        "walletCents", world.walletBalanceCents(player),
                        "you", world.gameSnapshot(token).get("you")));
                return;
            }
            case "/api/deposit_gold": {
                long cents = world.depositGold(player, Util.numLong(body.get("amountCents")));
                world.flush();
                respondJson(ex, 200, Map.of(
                        "ok", true,
                        "cents", cents,
                        "walletCents", world.walletBalanceCents(player),
                        "you", world.gameSnapshot(token).get("you")));
                return;
            }
            case "/api/withdraw_gold": {
                long cents = world.withdrawGold(player, Util.numLong(body.get("amountCents")));
                world.flush();
                respondJson(ex, 200, Map.of(
                        "ok", true,
                        "cents", cents,
                        "walletCents", world.walletBalanceCents(player),
                        "you", world.gameSnapshot(token).get("you")));
                return;
            }
            default:
                throw new ApiException(404, "Unknown endpoint: " + path);
        }
        world.flush();
        respondJson(ex, 200, Map.of(
                "ok", true,
                "you", world.gameSnapshot(token).get("you")));
    }

    private Player requirePlayer(String token) {
        Player p = world.findPlayerByToken(token);
        if (p == null) {
            throw new ApiException(401, "Not authenticated; join or resume a session.");
        }
        return p;
    }

    private static String str(Object o) {
        return o == null ? "" : o.toString();
    }
}
