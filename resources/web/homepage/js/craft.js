function loadCraftData()
{
    let xhr = new XMLHttpRequest();
    let craftHeader = document.getElementById("craftHeader");
    craftHeader.style.display = "none";
		craftHeader.innerHTML = '';
    xhr.open("GET", "https://craftbot.com/api/news/v1", true);
    xhr.onreadystatechange = function() {
      if (xhr.readyState === 4 && xhr.status === 200) {
        try {
          let data = JSON.parse(xhr.responseText);
          if(data != false) {
		    		craftHeader.style.display = "flex";
	          let para = document.createElement("p");
	          para.textContent = data.content;
	          craftHeader.appendChild(para);
	          craftHeader.addEventListener("click", function(e) {
		          OpenExternalURL(data.link);
	          })
          }
        } catch (e) {
          console.error("Error parsing JSON!", e);
        }
      }
    };
    xhr.send();
}

document.addEventListener("DOMContentLoaded", function(event) {
	loadCraftData();
});

// window.onfocus = loadCraftData;
