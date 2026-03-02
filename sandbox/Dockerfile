# Project-specific sandbox image — extends the generic base.
FROM claude-sandbox-base:latest

USER root

# Add project-specific setup here.
# Example: COPY sandbox.env /etc/sandbox.env

USER agent

CMD ["tmux", "new-session", "-s", "main", "claude", "--dangerously-skip-permissions"]
