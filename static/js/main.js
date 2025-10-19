let lastDestination = "";

document.addEventListener("DOMContentLoaded", function() {
	// Auto-calculate number of days from date pickers
	const fromDateInput = document.getElementById("from_date");
	const toDateInput = document.getElementById("to_date");
	const daysInput = document.getElementById("days");

	function updateDays() {
		const from = new Date(fromDateInput.value);
		const to = new Date(toDateInput.value);
		if (fromDateInput.value && toDateInput.value && to >= from) {
			// Calculate days (inclusive)
			const diff = Math.round((to - from) / (1000 * 60 * 60 * 24)) + 1;
			daysInput.value = diff;
		}
	}
	fromDateInput.addEventListener("change", updateDays);
	toDateInput.addEventListener("change", updateDays);
	const form = document.getElementById("tripForm");
	const aiSummary = document.getElementById("aiSummary");
	const loader = document.getElementById("loader");
	const exportBtn = document.getElementById("exportBtn");
	const mapsBtn = document.getElementById("mapsBtn");


	form.addEventListener("submit", function(e) {
		e.preventDefault();
		aiSummary.textContent = "";
		loader.style.display = "block";

		const destination = document.getElementById("destination").value;
		lastDestination = destination;
		const from_date = document.getElementById("from_date").value;
		const to_date = document.getElementById("to_date").value;
		const days = document.getElementById("days").value;
		const budget = document.getElementById("budget").value;
		const interests = Array.from(document.querySelectorAll('input[name="interests"]:checked')).map(i => i.value);

		fetch("/generate_trip", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ destination, from_date, to_date, days, budget, interests })
		})
		.then(res => res.json())
		.then(data => {
			loader.style.display = "none";
			aiSummary.textContent = data.summary || "No summary generated.";
		})
		.catch(() => {
			loader.style.display = "none";
			aiSummary.textContent = "Error generating itinerary. Please try again.";
		});
	});

	exportBtn.addEventListener("click", function() {
		window.location.href = "/export_page";
	});

	mapsBtn.addEventListener("click", function() {
		if (lastDestination) {
			window.open(`https://www.google.com/maps/search/?api=1&query=attractions+in+${encodeURIComponent(lastDestination)}`);
		} else {
			alert("Please generate a plan first.");
		}
	});
});