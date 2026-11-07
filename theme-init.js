// Sets data-theme on <html> before first paint, so the page never flashes the wrong
// palette. Loaded as a blocking script in <head>; app.js draws the toggle.
try{var t=localStorage.getItem("theme");if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",t)}catch(e){}
