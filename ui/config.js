// Where the two services are. This file is the local default (the ports docker-compose publishes);
// on Azure the deploy pipeline overwrites it with the public URLs of the two Container Apps.
window.MANAGEEAT_CONFIG = {
  PERSONNEL_URL: "http://localhost:8001",
  SALES_URL: "http://localhost:8002",
};
