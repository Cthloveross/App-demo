document.addEventListener("DOMContentLoaded", () => {
    // Handle Login
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;

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
        });
    }
    
    // Fetch Wardrobe Items
    if (document.getElementById("wardrobe-items")) {
        fetch("/api/wardrobe")
            .then(res => res.json())
            .then(data => console.log(data));
    }
    
    // Get AI Recommendation
    window.getRecommendation = function() {
        fetch("/api/recommendation")
            .then(res => res.json())
            .then(data => document.getElementById("recommendation").innerText = data.recommendation);
    };
});
