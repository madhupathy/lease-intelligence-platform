package com.leaseintel.riskengine.controller;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    @Value("${app.version}")
    private String version;

    @GetMapping("/api/alerts/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "version", version);
    }
}
