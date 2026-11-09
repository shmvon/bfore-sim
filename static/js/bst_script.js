document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('toggleHeader').addEventListener('click', function() {
        var myDiv = document.getElementById('myDiv');
        var toggleHeader = document.getElementById('toggleHeader');
    
        if (myDiv.style.display === 'none') {
            myDiv.style.display = 'block';
            toggleHeader.style.backgroundColor = 'transparent';
        } else {
            myDiv.style.display = 'none';
            toggleHeader.style.backgroundColor = 'blue';
        }
    });
});


// Find all elements with the class "tooltiptext"
var tooltips = document.querySelectorAll('.tooltiptext');

// Loop through each tooltip and add the 'long' class if its length > 30
tooltips.forEach(tooltip => {
  if (tooltip.textContent.length > 30) {
    tooltip.classList.add('long');
  }
});