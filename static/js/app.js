(function () {
    "use strict";

    function isoVersFr(valeur) {
        if (!valeur) {
            return "";
        }
        const m = valeur.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!m) {
            return valeur;
        }
        return m[3] + "/" + m[2] + "/" + m[1];
    }

    function normaliserDateFr(valeur) {
        valeur = valeur.trim();
        if (!valeur) {
            return "";
        }
        const parts = valeur.split(/[\s/.\-]+/).filter(Boolean);
        if (parts.length !== 3) {
            return valeur;
        }
        const jour = parts[0];
        const mois = parts[1];
        const annee = parts[2];
        if (!/^\d{1,2}$/.test(jour) || !/^\d{1,2}$/.test(mois) || !/^\d{4}$/.test(annee)) {
            return valeur;
        }
        return jour.padStart(2, "0") + "/" + mois.padStart(2, "0") + "/" + annee;
    }

    function frVersIso(valeur) {
        const m = valeur.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (!m) {
            return "";
        }
        return m[3] + "-" + m[2] + "-" + m[1];
    }

    function setSelectValue(select, value) {
        if (!value) {
            return;
        }
        let trouve = false;
        for (const option of select.options) {
            if (option.value === value) {
                trouve = true;
                break;
            }
        }
        if (!trouve) {
            const opt = document.createElement("option");
            opt.value = value;
            opt.textContent = value;
            select.appendChild(opt);
        }
        select.value = value;
    }

    (function initProgress() {
        let barre = document.getElementById("page-progress");
        if (!barre) {
            barre = document.createElement("div");
            barre.id = "page-progress";
            document.body.appendChild(barre);
        }
        barre.style.position = "fixed";
        barre.style.top = "0";
        barre.style.left = "0";
        barre.style.width = "0%";
        barre.style.height = "4px";
        barre.style.backgroundColor = "#F5C518";
        barre.style.zIndex = "2000";
        barre.style.transition = "width 0.3s ease";

        function demarrer() {
            barre.style.width = "0%";
            void barre.offsetWidth;
            barre.style.width = "80%";
        }

        function terminer() {
            barre.style.width = "100%";
            setTimeout(function () {
                barre.style.width = "0%";
            }, 250);
        }

        document.addEventListener("click", function (e) {
            const lien = e.target.closest("a[href]");
            if (lien && lien.target !== "_blank" && !lien.getAttribute("href").startsWith("#")) {
                demarrer();
            }
        });

        document.addEventListener("submit", function () {
            demarrer();
        });

        window.addEventListener("pageshow", terminer);
    })();

    (function initMenu() {
        const toggle = document.getElementById("menu-toggle");
        const menu = document.getElementById("mobile-menu");
        if (!toggle || !menu) {
            return;
        }
        toggle.addEventListener("click", function (e) {
            e.stopPropagation();
            menu.classList.toggle("open");
        });
        document.addEventListener("click", function (e) {
            if (!menu.contains(e.target) && !toggle.contains(e.target)) {
                menu.classList.remove("open");
            }
        });
    })();

    (function initExportDropdown() {
        const toggle = document.getElementById("export-toggle");
        const menu = document.getElementById("export-menu");
        if (!toggle || !menu) {
            return;
        }
        toggle.addEventListener("click", function (e) {
            e.stopPropagation();
            menu.classList.toggle("open");
        });
        document.addEventListener("click", function (e) {
            if (!menu.contains(e.target) && !toggle.contains(e.target)) {
                menu.classList.remove("open");
            }
        });
    })();

    (function initAjouter() {
        const btn = document.getElementById("btn-analyser");
        if (!btn) {
            return;
        }
        const loader = document.getElementById("loader");
        const errorBox = document.getElementById("error-box");
        const confirmSection = document.getElementById("confirm-section");
        const selectSource = document.getElementById("source");
        const sourceAutreWrap = document.getElementById("source-autre-wrap");
        const champSourceAutre = document.getElementById("source_autre");
        const formConfirmer = document.getElementById("form-confirmer");
        const champDate = document.getElementById("date_candidature");
        const selectTypeCandidature = document.getElementById("type_candidature");
        const contactFieldsWrap = document.getElementById("contact-fields-wrap");
        const checkboxEntreprise = document.getElementById("enregistrer_entreprise");
        const entrepriseFieldsWrap = document.getElementById("entreprise-fields-wrap");

        function majAffichageSourceAutre() {
            if (sourceAutreWrap && selectSource) {
                sourceAutreWrap.style.display = selectSource.value === "Autre" ? "block" : "none";
            }
        }

        function majAffichageContact() {
            if (contactFieldsWrap && selectTypeCandidature) {
                contactFieldsWrap.style.display =
                    selectTypeCandidature.value === "Candidature spontanée - Personne" ? "flex" : "none";
            }
        }

        function majAffichageEntreprise() {
            if (entrepriseFieldsWrap && checkboxEntreprise) {
                entrepriseFieldsWrap.style.display = checkboxEntreprise.checked ? "flex" : "none";
            }
        }

        async function analyser() {
            const texte = document.getElementById("texte").value.trim();
            const lienSource = document.getElementById("lien_source").value.trim();

            errorBox.classList.remove("show");
            errorBox.textContent = "";

            if (!texte) {
                errorBox.textContent = "Veuillez décrire votre candidature avant d'analyser.";
                errorBox.classList.add("show");
                return;
            }

            btn.disabled = true;
            loader.classList.add("show");
            confirmSection.classList.remove("show");

            try {
                const formData = new FormData();
                formData.append("texte", texte);

                const reponse = await fetch("/ajouter", {
                    method: "POST",
                    body: formData
                });

                const data = await reponse.json();

                if (!reponse.ok || data.erreur) {
                    throw new Error(data.erreur || "L'analyse a échoué. Réessayez.");
                }

                document.getElementById("entreprise").value = data.entreprise || "";
                document.getElementById("poste").value = data.poste || "";
                document.getElementById("localisation").value = data.localisation || "";
                document.getElementById("date_candidature").value = isoVersFr(data.date_candidature);
                document.getElementById("notes").value = data.notes || "";
                document.getElementById("lien_offre").value = lienSource || data.lien_offre || "";

                setSelectValue(document.getElementById("type_contrat"), data.type_contrat);
                setSelectValue(document.getElementById("statut"), data.statut || "En attente");
                setSelectValue(selectSource, data.source || "Autre");
                majAffichageSourceAutre();

                if (selectTypeCandidature) {
                    selectTypeCandidature.value = data.type_candidature || "Offre publiée";
                }
                if (document.getElementById("contact_nom")) {
                    document.getElementById("contact_nom").value = data.contact_nom || "";
                }
                if (document.getElementById("contact_lien")) {
                    document.getElementById("contact_lien").value = data.contact_lien || "";
                }
                majAffichageContact();

                if (document.getElementById("ent_nom")) {
                    document.getElementById("ent_nom").value = data.entreprise || "";
                }
                if (document.getElementById("ent_telephone")) {
                    document.getElementById("ent_telephone").value = data.telephone || "";
                }
                if (document.getElementById("ent_email")) {
                    document.getElementById("ent_email").value = data.email || "";
                }

                confirmSection.classList.add("show");
                confirmSection.scrollIntoView({ behavior: "smooth" });
            } catch (erreur) {
                errorBox.textContent = erreur.message;
                errorBox.classList.add("show");
            } finally {
                loader.classList.remove("show");
                btn.disabled = false;
            }
        }

        btn.addEventListener("click", analyser);

        if (champDate) {
            champDate.addEventListener("blur", function () {
                champDate.value = normaliserDateFr(champDate.value);
            });
        }

        if (selectSource) {
            selectSource.addEventListener("change", majAffichageSourceAutre);
        }

        if (selectTypeCandidature) {
            selectTypeCandidature.addEventListener("change", majAffichageContact);
            majAffichageContact();
        }

        if (checkboxEntreprise) {
            checkboxEntreprise.addEventListener("change", majAffichageEntreprise);
            majAffichageEntreprise();
        }

        if (formConfirmer) {
            formConfirmer.addEventListener("submit", function () {
                if (selectSource && selectSource.value === "Autre") {
                    const precision = champSourceAutre.value.trim();
                    if (precision) {
                        setSelectValue(selectSource, precision);
                    }
                }
            });
        }
    })();

    (function initDetail() {
        const formModifier = document.getElementById("form-modifier");
        if (!formModifier) {
            return;
        }
        const selectStatut = document.getElementById("statut");
        const blocEntretien = document.getElementById("bloc-entretien");
        const champDate = document.getElementById("entretien_date");
        const champHeure = document.getElementById("entretien_heure");
        const champHidden = document.getElementById("date_entretien");

        function majAffichageEntretien() {
            blocEntretien.style.display =
                selectStatut.value === "Entretien planifié" ? "block" : "none";
        }

        selectStatut.addEventListener("change", majAffichageEntretien);
        majAffichageEntretien();

        if (champDate) {
            champDate.addEventListener("blur", function () {
                champDate.value = normaliserDateFr(champDate.value);
            });
        }

        formModifier.addEventListener("submit", function () {
            const iso = frVersIso(normaliserDateFr(champDate.value));
            if (iso) {
                const heure = champHeure.value || "00:00";
                champHidden.value = iso + "T" + heure;
            } else {
                champHidden.value = "";
            }
        });
    })();

    (function initEntreprises() {
        const fab = document.getElementById("fab-ajout");
        const form = document.getElementById("form-entreprise");
        if (!fab || !form) {
            return;
        }
        fab.addEventListener("click", function (e) {
            e.preventDefault();
            form.scrollIntoView({ behavior: "smooth" });
            const premier = document.getElementById("nom");
            if (premier) {
                premier.focus();
            }
        });
    })();
})();
