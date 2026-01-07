module.exports = {
  apps: [{
    name: "monitoring-agent",
    script: "agent.py",
    // Interpreter: 'python3' is standard for Linux. 
    // If using a virtualenv, provide absolute path e.g. '/home/user/agent/venv/bin/python'
    interpreter: "python3", 
    args: "--config agent.config.json",
    cwd: ".",
    autorestart: true,
    watch: false,
    max_memory_restart: "200M",
    env: {
      PYTHONUNBUFFERED: "1",
      // If needed, set explicit path for config or other env vars
    }
  }]
};
