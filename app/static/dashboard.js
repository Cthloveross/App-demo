// dashboard.js

async function fetchSensorData(sensorType) {
    const response = await fetch(`/api/${sensorType}`);
    const data = await response.json();
    return data.data.map(entry => ({
        timestamp: entry[2],  // Assuming timestamp is at index 2
        value: entry[0]        // Assuming value is at index 0
    }));
}

async function createChart(sensorType, canvasId, label) {
    const sensorData = await fetchSensorData(sensorType);
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: sensorData.map(entry => entry.timestamp),
            datasets: [{
                label: label,
                data: sensorData.map(entry => entry.value),
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Timestamp' } },
                y: { title: { display: true, text: 'Value' } }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    createChart('temperature', 'temperatureChart', 'Temperature');
    createChart('humidity', 'humidityChart', 'Humidity');
    createChart('light', 'lightChart', 'Light Intensity');
});
