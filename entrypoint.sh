#!/bin/bash
# Entrypoint script for Safe Repo Bot
# Handles proper initialization and process management

set -e

# Log function for consistent output
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
}

# Wait for dependencies (if any) to be ready
wait_for_deps() {
    log "Checking if dependencies are ready..."
    # Add any dependency checks here (e.g., MongoDB connection)
    log "All dependencies are ready"
}

# Main function
main() {
    log "Starting Safe Repo Bot..."
    
    # Wait for dependencies
    wait_for_deps
    
    # Start process manager
    log "Starting process manager..."
    python3 process_manager.py
}

# Handle signals
trap 'log "Received SIGINT, shutting down..."; exit 0' INT
trap 'log "Received SIGTERM, shutting down..."; exit 0' TERM

# Execute main function
main "$@"
