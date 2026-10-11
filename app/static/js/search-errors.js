// Keep existing results visible when a database search fails.
document.addEventListener('htmx:beforeSwap', function(event) {
  const code = event.detail.xhr.getResponseHeader('X-Search-Error');
  if ((event.detail.xhr.status === 504 && code === 'search_timeout') ||
      (event.detail.xhr.status === 500 && code === 'search_failed')) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});
document.addEventListener('htmx:afterRequest', function(event) {
  const path = new URL(event.detail.requestConfig.path, window.location.href).pathname;
  if (event.detail.xhr.status >= 200 && event.detail.xhr.status < 300 &&
      path.startsWith('/search/')) {
    const panel = document.getElementById('search-error');
    if (panel) panel.replaceChildren();
  }
});
