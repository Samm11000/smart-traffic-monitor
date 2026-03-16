#!/bin/bash
echo "Starting Smart Traffic Monitor on EC2..."
cd /home/ubuntu/smart-traffic-monitor/smart-traffic-monitor
git pull origin main
docker-compose down
docker-compose up --build -d
echo ""
echo "Done! Services are live:"
echo "Dashboard : http://$(curl -s ifconfig.me):8501"
echo "Fog API   : http://$(curl -s ifconfig.me):5000/data"
echo "Health    : http://$(curl -s ifconfig.me):5000/health"