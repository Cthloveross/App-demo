async function fetchSensorData(sensorType) {
    try {
        const response = await fetch(`/api/${sensorType}`);
        const data = await response.json();

        if (!data.data || data.data.length === 0) {
            console.warn(`No data available for ${sensorType}`);
            return [];
        }

        return data.data.map(entry => ({
            timestamp: new Date(entry[0]),  // Timestamp is at index 0
            value: parseFloat(entry[1])      // Value is at index 1
        }));
    } catch (error) {
        console.error(`Error fetching data for ${sensorType}:`, error);
        return [];
    }
}

async function createChart(sensorType, canvasId, label, unit) {
    const sensorData = await fetchSensorData(sensorType);
    if (sensorData.length === 0) {
        console.warn(`Skipping chart for ${sensorType} due to no data.`);
        return;
    }

    const ctx = document.getElementById(canvasId).getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: sensorData.map(entry => entry.timestamp.toLocaleString()), // Format timestamp
            datasets: [{
                label: `${label} (${unit})`,
                data: sensorData.map(entry => entry.value),
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                pointRadius: 4,   // Add points to each data entry
                pointHoverRadius: 6,
                tension: 0.4      // Smoother curve
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { font: { size: 14 } } }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Timestamp', font: { size: 14 } },
                    ticks: { maxTicksLimit: 6, font: { size: 12 } }
                },
                y: {
                    title: { display: true, text: `Value (${unit})`, font: { size: 14 } },
                    ticks: { font: { size: 12 } }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    createChart('temperature', 'temperatureChart', 'Temperature', '°C');
    createChart('humidity', 'humidityChart', 'Humidity', '%');
    createChart('light', 'lightChart', 'Light Intensity', 'lux');
});
