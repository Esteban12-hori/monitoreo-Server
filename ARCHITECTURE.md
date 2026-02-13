# Arquitectura del Sistema Monitor Integral

Este documento describe la arquitectura del sistema de monitoreo de servidores ServPulse.

## Diagrama de Flujo de Datos

```mermaid
graph TD
    subgraph "Servidores Monitoreados (Agentes)"
        Agent1[Agente Python] -->|POST /api/metrics| API
        Agent2[Agente Python] -->|POST /api/metrics| API
        Docker[Docker Containers] -.->|Stats| Agent1
    end

    subgraph "Backend (FastAPI)"
        API[Servidor FastAPI]
        Auth[Autenticación JWT]
        AlertEngine[Motor de Alertas]
        DB[(SQLite Database)]
        
        API --> DB
        API --> Auth
        API --> AlertEngine
    end

    subgraph "Frontend (React)"
        Dashboard[Dashboard Web] -->|GET /api/metrics/history| API
        Dashboard -->|GET /api/servers| API
        AdminPanel[Panel Admin] -->|POST /api/admin/users| API
    end

    subgraph "Notificaciones"
        AlertEngine -->|SMTP| Email[Servidor de Correo]
        Email -->|Alert| UserEmail[Usuario]
    end

    %% Relaciones adicionales
    Auth -.->|Valida Tokens| Dashboard
    Auth -.->|Valida Tokens| AdminPanel
```

## Componentes Principales

### 1. Agente (Agent)
- Script en Python que se ejecuta en cada servidor monitoreado.
- Recopila métricas de CPU, RAM, Disco y Red.
- Envía datos periódicamente al servidor central vía HTTP POST.

### 2. Backend (Server)
- Construido con **FastAPI**.
- Maneja la ingestión de métricas, autenticación de usuarios y lógica de negocios.
- **Base de Datos**: SQLite (usando SQLAlchemy) para almacenar usuarios, configuración de servidores, historial de métricas y reglas de alertas.
- **Motor de Alertas**: Verifica umbrales (Thresholds) cada vez que llegan métricas y envía correos si se superan.

### 3. Frontend (Dashboard)
- Aplicación de una sola página (SPA) construida con **React** (sin build step complejo, servido estáticamente).
- Permite visualizar métricas en tiempo real, gestionar usuarios (admin) y configurar reglas de alerta.
- Utiliza **Chart.js** para gráficos históricos.

### 4. Seguridad
- Autenticación basada en **JWT** (JSON Web Tokens).
- Los agentes se autentican implícitamente por ID de servidor (modelo de confianza simple por ahora, se recomienda VPN/Firewall).
- Los usuarios tienen roles (Admin/User) que restringen el acceso a ciertas funcionalidades.
