"""
UI panel rendering for review and preview functionality.

This module contains functions to inject JavaScript-based UI panels into web pages
for reviewing data during form filling operations.
"""
from typing import Any, Dict, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver

from ..models import PolicyData


class ReviewPanelManager:
    """
    Manager for JavaScript-based review panels that display data during form filling.
    
    Panels support navigation between multiple views and can be collapsed/expanded.
    """
    
    def __init__(self, driver: WebDriver):
        """
        Initialize the panel manager.
        
        Args:
            driver: WebDriver instance
        """
        self.driver = driver
    
    def show_review_panel(self, title: str, rows: List[Tuple[str, Any]]) -> None:
        """
        Show a review panel with navigable data views.
        
        Creates or updates a fixed-position panel with previous/next navigation
        between different data views (Condiciones, Vehículo, Costos, etc.).
        
        Args:
            title: Title for this panel view
            rows: List of (label, value) tuples to display
        """
        try:
            js = r"""
            (function(titleArg, rowsArg){
              var id = 'absa-review-panel';
              var host = document.getElementById(id);
              if (!host) {
                host = document.createElement('div');
                host.id = id;
                host.style.position = 'fixed';
                host.style.top = '12px';
                host.style.right = '12px';
                host.style.zIndex = '2147483647';
                host.style.maxWidth = '420px';
                host.style.minWidth = '260px';
                host.style.background = 'rgba(21,22,25,0.92)';
                host.style.color = '#e9eef3';
                host.style.font = '12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, sans-serif';
                host.style.borderRadius = '10px';
                host.style.boxShadow = '0 8px 24px rgba(0,0,0,0.35)';
                host.style.overflow = 'hidden';
                document.documentElement.appendChild(host);
              }
              function esc(x){ return String(x == null ? '' : x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
              // Global deck structure for panes
              var deck = window.__absaDeck;
              if (!deck) { deck = window.__absaDeck = { list: [], index: 0 }; }
              function upsertPane(title, rows){
                var idx = -1;
                for (var i=0;i<deck.list.length;i++){ if (deck.list[i].title === title) { idx = i; break; } }
                var pane = { title: String(title||''), rows: Array.isArray(rows) ? rows : [] };
                if (idx === -1) { deck.list.push(pane); deck.index = deck.list.length - 1; }
                else { deck.list[idx] = pane; deck.index = idx; }
              }
              function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }
              function render(){
                var total = deck.list.length;
                var idx = clamp(deck.index, 0, Math.max(0,total-1));
                deck.index = idx;
                var pane = total ? deck.list[idx] : { title:'', rows:[] };
                var bodyRows = '';
                for (var i=0;i<pane.rows.length;i++){
                  var k = pane.rows[i][0]; var v = pane.rows[i][1];
                  bodyRows += '<tr>'+
                    '<td style="padding:6px 8px;color:#b7c0c7;white-space:nowrap">'+esc(k)+'</td>'+
                    '<td style="padding:6px 8px;color:#e9eef3;word-break:break-word">'+esc(v)+'</td>'+
                  '</tr>';
                }
                host.innerHTML = ''+
                  '<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#17181b;border-bottom:1px solid #2b2f36">'+
                    '<button id="absa-prev" title="Anterior" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">◀</button>'+
                    '<strong style="font-size:13px">'+esc(pane.title || '')+'</strong>'+
                    '<span style="margin-left:auto;color:#b7c0c7">'+ (total? (String(idx+1)+'/'+String(total)) : '') +'</span>'+
                    '<button id="absa-collapse" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">▲</button>'+
                    '<button id="absa-next" title="Siguiente" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">▶</button>'+
                    '<button id="absa-close" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">×</button>'+
                  '</div>'+
                  '<div id="absa-body" style="max-height:52vh;overflow:auto">'+
                    '<table style="border-collapse:collapse;width:100%">'+ bodyRows +'</table>'+
                  '</div>';
                var btnClose = host.querySelector('#absa-close');
                var btnCol = host.querySelector('#absa-collapse');
                var btnPrev = host.querySelector('#absa-prev');
                var btnNext = host.querySelector('#absa-next');
                var body = host.querySelector('#absa-body');
                btnClose.onclick = function(){ host.remove(); };
                btnCol.onclick = function(){ var collapsed = body.style.display === 'none'; body.style.display = collapsed ? '' : 'none'; btnCol.textContent = collapsed ? '▲' : '▼'; };
                btnPrev.onclick = function(){ if (deck.list.length) { deck.index = (deck.index - 1 + deck.list.length) % deck.list.length; render(); } };
                btnNext.onclick = function(){ if (deck.list.length) { deck.index = (deck.index + 1) % deck.list.length; render(); } };
              }
              upsertPane(titleArg, rowsArg);
              render();
            })(arguments[0], arguments[1]);
            """
            js_rows = [[str(k), ('' if v is None else v)] for (k, v) in rows]
            self.driver.execute_script(js, title, js_rows)
        except Exception:
            pass
    
    def show_preview_condiciones(self, data: PolicyData) -> None:
        """
        Show preview panel for Condiciones tab data.
        
        Args:
            data: PolicyData instance with condition fields
        """
        rows: List[Tuple[str, Any]] = [
            ("productor", getattr(data, "productor", None)),
            ("cliente", getattr(data, "cliente", None)),
            ("aseguradora", getattr(data, "aseguradora", None)),
            ("riesgo", getattr(data, "riesgo", None)),
            ("moneda", getattr(data, "moneda", None)),
            ("tipo_contacto_ssn", getattr(data, "tipo_contacto_ssn", None)),
            ("tipo_iva", getattr(data, "tipo_iva", None)),
            ("tipo_renovacion", getattr(data, "tipo_renovacion", None)),
            ("clausula_ajuste", getattr(data, "clausula_ajuste", None)),
            ("cant_cuotas", getattr(data, "cant_cuotas", None)),
            ("tipo_vigencia", getattr(data, "tipo_vigencia", None)),
            ("inicio_vigencia", getattr(data, "inicio_vigencia", None)),
            ("refacturacion", getattr(data, "refacturacion", None)),
        ]
        self.show_review_panel("Condiciones (revisión)", rows)
    
    def show_preview_item(self, data: PolicyData) -> None:
        """
        Show preview panel for vehicle item data.
        
        Args:
            data: PolicyData instance with vehicle fields
        """
        rows: List[Tuple[str, Any]] = [
            ("anio", getattr(data, "anio", None)),
            ("marca", getattr(data, "marca", None)),
            ("patente", getattr(data, "patente", None)),
            ("chasis", getattr(data, "chasis", None)),
            ("motor", getattr(data, "motor", None)),
        ]
        self.show_review_panel("Item Vehículo (revisión)", rows)
    
    def show_preview_condiciones_dict(self, data: Dict[str, Any]) -> None:
        """
        Show preview panel for Condiciones tab data from dictionary.
        
        Args:
            data: Dictionary with condition fields
        """
        rows: List[Tuple[str, Any]] = [
            ("productor", data.get("productor")),
            ("cliente", data.get("cliente")),
            ("aseguradora", data.get("aseguradora")),
            ("riesgo", data.get("riesgo")),
            ("moneda", data.get("moneda")),
            ("tipo_contacto_ssn", data.get("tipo_contacto_ssn")),
            ("tipo_iva", data.get("tipo_iva")),
            ("tipo_renovacion", data.get("tipo_renovacion")),
            ("clausula_ajuste", data.get("clausula_ajuste")),
            ("cant_cuotas", data.get("cant_cuotas")),
            ("tipo_vigencia", data.get("tipo_vigencia")),
            ("inicio_vigencia", data.get("inicio_vigencia")),
            ("refacturacion", data.get("refacturacion")),
        ]
        self.show_review_panel("Condiciones (revisión)", rows)
    
    def show_preview_item_dict(self, data: Dict[str, Any]) -> None:
        """
        Show preview panel for vehicle item data from dictionary.
        
        Args:
            data: Dictionary with vehicle fields
        """
        rows: List[Tuple[str, Any]] = [
            ("anio", data.get("anio")),
            ("marca", data.get("marca")),
            ("patente", data.get("patente")),
            ("chasis", data.get("chasis")),
            ("motor", data.get("motor")),
        ]
        self.show_review_panel("Item Vehículo (revisión)", rows)
    
    def install_costos_preview_dict(self, data: Dict[str, Any]) -> None:
        """
        Install automatic preview watcher for Costos tab.
        
        Sets up event listeners that automatically show costs preview
        when the Costos tab becomes active. Only installs once per page.
        
        Args:
            data: Dictionary with prima_total and premio_total
        """
        prima = data.get("prima_total")
        premio = data.get("premio_total")
        try:
            js = r"""
            (function(primaArg, premioArg){
              if (window.__absaCostsWatcherInstalled) return;
              window.__absaCostsWatcherInstalled = true;

              if (!window.__absaRenderPanel) {
                window.__absaRenderPanel = function(title, rows){
                  var id = 'absa-review-panel';
                  var host = document.getElementById(id);
                  if (!host) {
                    host = document.createElement('div');
                    host.id = id;
                    host.style.position = 'fixed';
                    host.style.top = '12px';
                    host.style.right = '12px';
                    host.style.zIndex = '2147483647';
                    host.style.maxWidth = '420px';
                    host.style.minWidth = '260px';
                    host.style.background = 'rgba(21,22,25,0.92)';
                    host.style.color = '#e9eef3';
                    host.style.font = '12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, sans-serif';
                    host.style.borderRadius = '10px';
                    host.style.boxShadow = '0 8px 24px rgba(0,0,0,0.35)';
                    host.style.overflow = 'hidden';
                    document.documentElement.appendChild(host);
                  }
                  function esc(x){ return String(x == null ? '' : x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
                  var bodyRows = '';
                  for (var i=0;i<rows.length;i++) {
                    var k = rows[i][0], v = rows[i][1];
                    bodyRows += '<tr>'+
                      '<td style="padding:6px 8px;color:#b7c0c7;white-space:nowrap">'+esc(k)+'</td>'+
                      '<td style="padding:6px 8px;color:#e9eef3;word-break:break-word">'+esc(v)+'</td>'+
                    '</tr>';
                  }
                  host.innerHTML = ''+
                    '<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#17181b;border-bottom:1px solid #2b2f36">'+
                      '<strong style="font-size:13px">'+esc(title)+'</strong>'+
                      '<span style="margin-left:auto"></span>'+
                      '<button id="absa-collapse" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">▲</button>'+
                      '<button id="absa-close" style="border:0;background:#2b2f36;color:#e9eef3;border-radius:6px;padding:3px 7px;cursor:pointer">×</button>'+
                    '</div>'+
                    '<div id="absa-body" style="max-height:52vh;overflow:auto">'+
                      '<table style="border-collapse:collapse;width:100%">'+ bodyRows +'</table>'+
                    '</div>';
                  var btnClose = host.querySelector('#absa-close');
                  var btnCol = host.querySelector('#absa-collapse');
                  var body = host.querySelector('#absa-body');
                  btnClose.onclick = function(){ host.remove(); };
                  btnCol.onclick = function(){ var c = body.style.display === 'none'; body.style.display = c ? '' : 'none'; btnCol.textContent = c ? '▲' : '▼'; };
                };
              }

              function showCosts(){
                window.__absaRenderPanel('Costos (revisión)', [
                  ['prima_total', String(primaArg == null ? '' : primaArg)],
                  ['premio_total', String(premioArg == null ? '' : premioArg)]
                ]);
              }

              function isCostsActive(){
                var li = document.getElementById('LitabCostos');
                if (li && li.classList.contains('active')) return true;
                var a = document.getElementById('tabCostos');
                if (a && (a.getAttribute('aria-expanded') === 'true')) return true;
                var pane = document.getElementById('TabCostos');
                if (pane && pane.offsetParent !== null) return true;
                return false;
              }

              // Hook for Bootstrap shown.bs.tab event
              try {
                if (window.jQuery && typeof jQuery === 'function') {
                  jQuery('#tabCostos, a[href="#TabCostos"]').on('shown.bs.tab', function () { setTimeout(showCosts, 0); });
                }
              } catch (e) {}

              // Direct click fallback
              document.addEventListener('click', function(ev){
                var t = ev.target; var a = t && t.closest ? t.closest('#tabCostos, a[href="#TabCostos"]') : null;
                if (a) setTimeout(showCosts, 60);
              }, true);

              // MutationObserver for class/aria/visibility changes
              try {
                var mo = new MutationObserver(function(){ if (isCostsActive()) showCosts(); });
                mo.observe(document.documentElement, {subtree:true, attributes:true, childList:true, attributeFilter:['class','aria-expanded','style']});
              } catch(e) {}
            })(arguments[0], arguments[1]);
            """
            self.driver.execute_script(js, prima, premio)
        except Exception:
            pass
    
    def show_preview_costos(self, data: Dict[str, Any]) -> None:
        """
        Show preview panel for costs data immediately.
        
        Args:
            data: Dictionary with prima_total and premio_total
        """
        rows: List[Tuple[str, Any]] = [
            ("prima_total", data.get("prima_total")),
            ("premio_total", data.get("premio_total")),
        ]
        self.show_review_panel("Costos (revisión)", rows)
