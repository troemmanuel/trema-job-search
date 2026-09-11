#!/bin/bash
# Setup script for macOS LaunchAgent Daily Job Search Cron

PLIST_NAME="com.trema.jobsearch.daily.plist"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_FILE="$TARGET_DIR/$PLIST_NAME"

echo "=== Configuration du Planificateur Quotidien macOS (Launchd) ==="

if [ "$1" == "uninstall" ]; then
    echo "Désinstallation de $PLIST_NAME..."
    launchctl unload "$TARGET_FILE" 2>/dev/null
    rm -f "$TARGET_FILE"
    echo "Planificateur désinstallé."
    exit 0
fi

mkdir -p "$TARGET_DIR"
mkdir -p "$SOURCE_DIR/../logs"

cp "$SOURCE_DIR/$PLIST_NAME" "$TARGET_FILE"

# Rechargement
launchctl unload "$TARGET_FILE" 2>/dev/null
launchctl load "$TARGET_FILE"

echo "✅ Planificateur quotidien installé et activé dans $TARGET_FILE"
echo "📅 Exécution automatique programmée chaque matin à 08:00"
echo "📄 Logs disponibles dans: $SOURCE_DIR/../logs/cron_daily.log"
