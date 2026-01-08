const CONFIG = {
  // Replace with your Render API URL after deployment
  // e.g., 'https://cjspanel-api.onrender.com'
  API_BASE_URL:
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
      ? "http://localhost:5000"
      : "https://cjspanel-api.onrender.com",
};
export default CONFIG;
