document.addEventListener("DOMContentLoaded", () => {
    console.log("Dashboard script loaded!");

    // Handle Login
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;

            try {
                const response = await fetch("/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username: email, password: password }),
                });

                if (response.ok) {
                    window.location.href = "/dashboard";
                } else {
                    alert("Invalid credentials");
                }
            } catch (error) {
                console.error("Login failed:", error);
                alert("Login error. Please try again.");
            }
        });
    }

    // Handle Signup
    const signupForm = document.getElementById("signup-form");
    if (signupForm) {
        signupForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const data = {
                username: document.getElementById("email").value,
                password: document.getElementById("password").value,
                location: document.getElementById("location").value,
            };

            try {
                const response = await fetch("/auth/signup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    window.location.href = "/login";
                } else {
                    alert("Signup failed");
                }
            } catch (error) {
                console.error("Signup error:", error);
                alert("Signup error. Please try again.");
            }
        });
    }

    // Fetch AI Recommendation
    async function getRecommendation() {
        const userPrompt = document.getElementById("userPrompt")?.value;

        if (!userPrompt?.trim()) {
            alert("Please enter a prompt before requesting advice.");
            return;
        }

        try {
            const response = await fetch(`/api/recommendation?prompt=${encodeURIComponent(userPrompt)}`);
            const data = await response.json();
            
            document.getElementById("recommendation").innerText = data.recommendation || "No response from AI.";
        } catch (error) {
            console.error("Error fetching AI recommendation:", error);
            document.getElementById("recommendation").innerText = "Failed to get advice. Please try again.";
        }
    }

    // Attach event listener to recommendation button if it exists
    const recommendationButton = document.querySelector("button[onclick='getRecommendation()']");
    if (recommendationButton) {
        recommendationButton.addEventListener("click", getRecommendation);
    }

    // Fetch and display Temperature Data
    async function fetchSensorData(sensorType) {
        try {
            const response = await fetch(`/api/${sensorType}`);
            const data = await response.json();

            return data.map(entry => ({
                timestamp: new Date(entry.timestamp),
                value: parseFloat(entry.value)
            }));
        } catch (error) {
            console.error(`Error fetching ${sensorType} data:`, error);
            return [];
        }
    }

    async function createTemperatureChart() {
        console.log("Creating chart for temperature...");
        const sensorData = await fetchSensorData('temperature');

        if (sensorData.length === 0) {
            console.warn("No temperature data found");
            return;
        }

        const ctx = document.getElementById('temperatureChart')?.getContext('2d');
        if (!ctx) {
            console.warn("Canvas element for temperature char