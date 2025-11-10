# 🧩 Sistema de Monitoreo Integral para Servidores Linux

Un sistema **modular y distribuido** de monitoreo en tiempo real para entornos Linux.  
Incluye agente ligero, API segura y un panel web interactivo con gráficos y alertas.

---

## 🚀 Características Principales

- 🐍 **Agente ligero (Python)**: recolecta métricas del sistema.  
- ⚙️ **Backend (FastAPI)**: gestiona almacenamiento, tokens y API segura.  
- 📊 **Dashboard Web (React + Chart.js)**: visualiza métricas en tiempo real e histórico.  
- 🧠 **Gestión de alertas**: define umbrales personalizados.  
- 🔐 **Autenticación y TLS**: tokens únicos y soporte de certificados autofirmados.

---

## 📈 Métricas Soportadas

| Categoría | Métricas |
|------------|-----------|
| **Memoria RAM** | Total, usada, libre, caché |
| **CPU** | Uso total y por núcleo |
| **Disco** | Espacio disponible, usado y porcentaje |
| **Docker** | Contenedores activos, estado y uso básico |

---

## 🏗️ Arquitectura del Sistema

