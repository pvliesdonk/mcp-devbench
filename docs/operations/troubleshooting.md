# Troubleshooting

Common issues and solutions.

## Container Won't Start

**Symptom:** Container fails to spawn

**Solutions:**
1. Check Docker is running
2. Verify image exists
3. Check image is in allow-list
4. Review container logs
5. Check resource limits

## High Memory Usage

**Symptom:** Server using too much memory

**Solutions:**
1. Reduce container count
2. Lower memory limits
3. Enable cleanup
4. Check for memory leaks

## Authentication Failures

**Symptom:** 401/403 errors

**Solutions:**
1. Verify token is correct
2. Check OIDC configuration
3. Review audit logs
4. Test with curl

## Database Errors

**Symptom:** Database connection failures

**Solutions:**
1. Check connection string
2. Verify database is running
3. Check permissions
4. Review migrations

## Docker Socket Permission

**Symptom:** Permission denied accessing Docker

**Solutions:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Or run as root (not recommended)
sudo python -m mcp_devbench.server
```

## Logs

Check logs for more details:

```bash
# Docker
docker logs mcp-devbench

# Systemd
journalctl -u mcp-devbench

# File
tail -f /var/log/mcp-devbench/server.log
```

## Getting Help

- **GitHub Issues:** [Report bugs](https://github.com/pvliesdonk/mcp-devbench/issues)
- **Discussions:** [Ask questions](https://github.com/pvliesdonk/mcp-devbench/discussions)
