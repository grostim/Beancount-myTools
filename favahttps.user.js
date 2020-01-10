// ==UserScript==
// @name         [Fava] all over https
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Rajoute une balise meta
// @icon         https://github.com/beancount/fava/raw/master/fava/static/images/favicon.ico
// @downloadURL  https://gitlab.com/BZHDeveloper/HFR/raw/master/multimp.user.js
// @updateURL    https://gitlab.com/BZHDeveloper/HFR/raw/master/multimp.user.js
// @author       You
// @match        https://fava.famillegros.com/*
// @require      http://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js
// @grant        GM_addStyle
// ==/UserScript==

(function() {
    'use strict';
    $("head").append ( `<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">` );
})();
