(() => {
  "use strict";
  const GA_ID = "G-VL62LP5NZ9";
  const ADS_CLIENT = "ca-pub-5757077530115290";
  const IMPACT_SRC = "https://utt.impactcdn.com/P-A7797224-727f-48f4-89dc-05dcedd192681.js";
  const KEY = "tf_privacy_consent_v1";
  const lang = (document.documentElement.lang || "en").toLowerCase().slice(0, 2);
  const copy = {
    en: ["Privacy preferences","We use essential storage to make this website work. With your permission, we also use Google Analytics to understand site traffic and, on selected pages, advertising technologies. You can accept, reject, or customize optional technologies. You can change your choice at any time.","Accept all","Reject optional","Settings","Essential","Required for core website functions and remembering your privacy choice.","Analytics","Allows Google Analytics to measure visits and page usage.","Advertising","Allows advertising and affiliate measurement technologies on selected pages.","Save my choices","Cancel","Privacy settings","Optional categories stay off unless you choose to enable them.","Always active"],
    fr: ["Préférences de confidentialité","Nous utilisons le stockage essentiel au fonctionnement du site. Avec votre permission, nous utilisons aussi Google Analytics pour mesurer l’audience et, sur certaines pages, des technologies publicitaires. Vous pouvez accepter, refuser ou personnaliser les technologies facultatives. Vous pouvez modifier votre choix en tout temps.","Tout accepter","Tout refuser","Paramètres","Essentiels","Nécessaires au fonctionnement du site et à la mémorisation de votre choix.","Mesure d’audience","Autorise Google Analytics à mesurer les visites et l’utilisation des pages.","Publicité","Autorise les technologies publicitaires et la mesure des liens partenaires sur certaines pages.","Enregistrer mes choix","Annuler","Paramètres de confidentialité","Les catégories facultatives restent désactivées tant que vous ne les activez pas.","Toujours actifs"],
    es: ["Preferencias de privacidad","Utilizamos almacenamiento esencial para que el sitio funcione. Con tu permiso, también utilizamos Google Analytics para comprender el tráfico y, en algunas páginas, tecnologías publicitarias. Puedes aceptar, rechazar o personalizar las tecnologías opcionales. Puedes cambiar tu elección en cualquier momento.","Aceptar todo","Rechazar opcionales","Configuración","Esenciales","Necesarias para el funcionamiento del sitio y para recordar tu elección.","Analítica","Permite que Google Analytics mida las visitas y el uso de las páginas.","Publicidad","Permite tecnologías publicitarias y medición de afiliados en algunas páginas.","Guardar mis opciones","Cancelar","Configuración de privacidad","Las categorías opcionales están desactivadas hasta que decidas activarlas.","Siempre activas"],
    de: ["Datenschutzeinstellungen","Wir verwenden notwendige Speichertechnologien für den Betrieb dieser Website. Mit Ihrer Zustimmung verwenden wir außerdem Google Analytics zur Messung der Nutzung und auf ausgewählten Seiten Werbetechnologien. Sie können optionale Technologien akzeptieren, ablehnen oder anpassen. Sie können Ihre Auswahl jederzeit ändern.","Alle akzeptieren","Optionale ablehnen","Einstellungen","Notwendig","Für grundlegende Website-Funktionen und zum Speichern Ihrer Auswahl erforderlich.","Analyse","Erlaubt Google Analytics, Besuche und Seitennutzung zu messen.","Werbung","Erlaubt Werbe- und Affiliate-Messungstechnologien auf ausgewählten Seiten.","Auswahl speichern","Abbrechen","Datenschutzeinstellungen","Optionale Kategorien bleiben deaktiviert, bis Sie sie einschalten.","Immer aktiv"]
  };
  const t = copy[lang] || copy.en;
  const advertisingPage = document.documentElement.dataset.siteAdvertising === "true";
  const impactPage = document.documentElement.dataset.siteImpact === "true";
  let saved = readChoice();
  let analyticsLoaded = false;
  let advertisingLoaded = false;

  function readChoice() {
    try {
      const v = JSON.parse(localStorage.getItem(KEY) || "null");
      if (v && typeof v.analytics === "boolean" && typeof v.advertising === "boolean") return v;
    } catch (_) {}
    return null;
  }
  function addStyles() {
    if (document.getElementById("tf-privacy-styles")) return;
    const s = document.createElement("style");
    s.id = "tf-privacy-styles";
    s.textContent = [
      "#tf-privacy-banner,#tf-privacy-settings{font-family:Arial,Helvetica,sans-serif;box-sizing:border-box}",
      "#tf-privacy-banner * ,#tf-privacy-settings *{box-sizing:border-box}",
      "#tf-privacy-banner{position:fixed;z-index:2147483000;left:16px;bottom:16px;width:min(760px,calc(100vw - 32px));padding:18px;background:#101b2b;color:#f7f9fc;border:1px solid #41516a;border-radius:14px;box-shadow:0 12px 42px #0006}",
      "#tf-privacy-banner h2,#tf-privacy-settings h2{font-size:18px;line-height:1.25;margin:0 0 8px;color:inherit}",
      "#tf-privacy-banner p,#tf-privacy-settings p{font-size:13px;line-height:1.55;margin:0 0 14px;color:#dce4ef}",
      ".tf-privacy-actions{display:flex;flex-wrap:wrap;gap:8px}",
      ".tf-privacy-actions button{flex:1 1 145px;min-height:40px;border:1px solid #aebbd0;border-radius:7px;padding:9px 12px;font-size:13px;font-weight:700;cursor:pointer}",
      ".tf-privacy-primary{background:#f4d34e;color:#111;border-color:#f4d34e!important}",
      ".tf-privacy-secondary{background:#17263b;color:#fff}",
      "#tf-privacy-settings{position:fixed;z-index:2147483001;inset:0;background:#0009;display:grid;place-items:center;padding:16px}",
      ".tf-privacy-dialog{width:min(560px,100%);max-height:min(88vh,760px);overflow:auto;background:#fff;color:#142033;border-radius:14px;padding:20px;box-shadow:0 18px 55px #0006}",
      ".tf-privacy-dialog h2{color:#142033}.tf-privacy-dialog p{color:#536174}",
      ".tf-privacy-row{display:flex;gap:14px;align-items:flex-start;padding:13px 0;border-top:1px solid #e5eaf0}",
      ".tf-privacy-row input{width:19px;height:19px;flex:0 0 19px;margin:2px 0 0;accent-color:#1b5c9b}",
      ".tf-privacy-row strong{display:block;font-size:14px;margin-bottom:3px}",
      ".tf-privacy-row small{display:block;color:#59677a;font-size:12px;line-height:1.45}",
      ".tf-privacy-locked{font-size:11px;color:#68768a;font-weight:700}",
      "#tf-privacy-settings-link{position:fixed;z-index:2147482000;left:12px;bottom:12px;background:#101b2b;color:#fff;border:1px solid #64748b;border-radius:20px;padding:8px 12px;font:12px Arial,sans-serif;cursor:pointer;box-shadow:0 3px 12px #0003}",
      "@media(max-width:520px){#tf-privacy-banner{left:8px;bottom:8px;width:calc(100vw - 16px);padding:14px}.tf-privacy-actions button{flex:1 1 100%}.tf-privacy-dialog{padding:16px}}"
    ].join("");
    document.head.appendChild(s);
  }
  function loadAnalytics() {
    if (analyticsLoaded) return;
    analyticsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function(){ window.dataLayer.push(arguments); };
    window.gtag("consent","default",{analytics_storage:"denied",ad_storage:"denied",ad_user_data:"denied",ad_personalization:"denied"});
    window.gtag("consent","update",{analytics_storage:"granted"});
    window.gtag("js",new Date());
    window.gtag("config",GA_ID,{anonymize_ip:true});
    const s=document.createElement("script"); s.async=true; s.src="https://www.googletagmanager.com/gtag/js?id="+GA_ID; s.referrerPolicy="strict-origin-when-cross-origin"; document.head.appendChild(s);
  }
  function loadAdvertising() {
    if (!advertisingPage || advertisingLoaded) return;
    advertisingLoaded = true;
    const a=document.createElement("script"); a.async=true; a.crossOrigin="anonymous"; a.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client="+ADS_CLIENT; document.head.appendChild(a);
    if (impactPage) {
      const i=document.createElement("script"); i.async=true; i.src=IMPACT_SRC;
      i.onload=()=>{try{if(window.impactStat){window.impactStat("transformLinks");window.impactStat("trackImpression");}}catch(_){}};
      document.head.appendChild(i);
    }
  }
  function clearAnalyticsCookies() {
    document.cookie.split(";").map(x=>x.trim().split("=")[0]).filter(n=>n==="_ga"||n==="_gid"||n==="_gat"||n.startsWith("_ga_")).forEach(n=>{
      document.cookie=n+"=; Max-Age=0; path=/";
      document.cookie=n+"=; Max-Age=0; path=/; domain="+location.hostname;
      document.cookie=n+"=; Max-Age=0; path=/; domain=.technofront.org";
    });
  }
  function closeBanner(){const b=document.getElementById("tf-privacy-banner");if(b)b.remove();}
  function showSettingsLink(){
    if(document.getElementById("tf-privacy-settings-link"))return;
    const b=document.createElement("button");b.id="tf-privacy-settings-link";b.type="button";b.textContent=t[13];b.addEventListener("click",openSettings);document.body.appendChild(b);
  }
  function saveChoice(choice){
    const next={analytics:!!choice.analytics,advertising:advertisingPage&&!!choice.advertising,updatedAt:new Date().toISOString()};
    const had=saved&& (saved.analytics||saved.advertising);
    const disabling=!!(had&&((saved.analytics&&!next.analytics)||(saved.advertising&&!next.advertising)));
    try{localStorage.setItem(KEY,JSON.stringify(next));}catch(_){}
    saved=next;
    if(disabling){
      if(window.gtag)window.gtag("consent","update",{analytics_storage:next.analytics?"granted":"denied",ad_storage:"denied",ad_user_data:"denied",ad_personalization:"denied"});
      if(!next.analytics)clearAnalyticsCookies();
      window.location.reload();return;
    }
    if(next.analytics)loadAnalytics();
    if(next.advertising)loadAdvertising();
    closeBanner();showSettingsLink();
  }
  function openSettings(){
    const old=document.getElementById("tf-privacy-settings");if(old)old.remove();
    const c=saved||{analytics:false,advertising:false};
    const w=document.createElement("div");w.id="tf-privacy-settings";
    w.innerHTML="<section class=\"tf-privacy-dialog\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"tf-privacy-title\">"+
      "<h2 id=\"tf-privacy-title\">"+t[0]+"</h2><p>"+t[14]+"</p>"+
      "<div class=\"tf-privacy-row\"><input type=\"checkbox\" checked disabled aria-label=\""+t[5]+"\"><div><strong>"+t[5]+"</strong><small>"+t[6]+"</small><span class=\"tf-privacy-locked\">Always active</span></div></div>"+
      "<label class=\"tf-privacy-row\"><input id=\"tf-privacy-analytics\" type=\"checkbox\" "+(c.analytics?"checked":"")+"><span><strong>"+t[7]+"</strong><small>"+t[8]+"</small></span></label>"+
      (advertisingPage?"<label class=\"tf-privacy-row\"><input id=\"tf-privacy-ads\" type=\"checkbox\" "+(c.advertising?"checked":"")+"><span><strong>"+t[9]+"</strong><small>"+t[10]+"</small></span></label>":"")+
      "<div class=\"tf-privacy-actions\"><button class=\"tf-privacy-secondary\" id=\"tf-privacy-cancel\" type=\"button\">"+t[12]+"</button><button class=\"tf-privacy-primary\" id=\"tf-privacy-save\" type=\"button\">"+t[11]+"</button></div></section>";
    w.addEventListener("click",e=>{if(e.target===w)w.remove();});document.body.appendChild(w);
    w.querySelector("#tf-privacy-cancel").addEventListener("click",()=>w.remove());
    w.querySelector("#tf-privacy-save").addEventListener("click",()=>{
      const ad=w.querySelector("#tf-privacy-ads");
      saveChoice({analytics:w.querySelector("#tf-privacy-analytics").checked,advertising:!!(ad&&ad.checked)});w.remove();
    });
  }
  function showBanner(){
    const b=document.createElement("section");b.id="tf-privacy-banner";b.setAttribute("role","region");b.setAttribute("aria-label",t[0]);
    b.innerHTML="<h2>"+t[0]+"</h2><p>"+t[1]+"</p><div class=\"tf-privacy-actions\">"+
      "<button class=\"tf-privacy-primary\" id=\"tf-privacy-accept\" type=\"button\">"+t[2]+"</button>"+
      "<button class=\"tf-privacy-secondary\" id=\"tf-privacy-reject\" type=\"button\">"+t[3]+"</button>"+
      "<button class=\"tf-privacy-secondary\" id=\"tf-privacy-customize\" type=\"button\">"+t[4]+"</button></div>";
    document.body.appendChild(b);
    b.querySelector("#tf-privacy-accept").addEventListener("click",()=>saveChoice({analytics:true,advertising:true}));
    b.querySelector("#tf-privacy-reject").addEventListener("click",()=>saveChoice({analytics:false,advertising:false}));
    b.querySelector("#tf-privacy-customize").addEventListener("click",openSettings);
  }
  function init(){
    addStyles();
    if(saved){if(saved.analytics)loadAnalytics();if(saved.advertising)loadAdvertising();showSettingsLink();}
    else showBanner();
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
})();