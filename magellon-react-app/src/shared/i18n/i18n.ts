import i18n from "i18next";
import ICU from 'i18next-icu';
import { initReactI18next } from "react-i18next";
// import en_admin from './locales/en/admin.json';
// import en_person from './locales/en/person.json';
// import fa_admin from './locales/fa/admin.json';
// import fa_person from './locales/fa/person.json';
import Backend from 'i18next-http-backend';

// the translations
// (tip move them in a JSON file and import them,
// or even better, manage them separated from your code: https://react.i18next.com/guides/multiple-translation-files)
// const resources = {
//     en: {
//         admin: en_admin,
//         person: en_person
//     },
//     fa: {admin : fa_admin,
//         person: fa_person
//     }
// };
i18n
    .use(ICU)
    .use(Backend)
    .use(initReactI18next)
    .init({
        lng:'en',
        fallbackLng: 'en',
        debug: true,
        interpolation: {
            escapeValue: false,
            skipOnVariables: false
        },
        backend: {
            // Modify the loadPath to match your new directory structure
            loadPath: '/locales/{{lng}}/{{ns}}.json', // {{ns}} will be replaced with the namespace (e.g., global, home, error, activate)
        },
        // ns: ['global', 'home',  'activate'], // Define the namespaces used in your application
        defaultNS: 'global', // Set the default namespace
    });

 i18n.changeLanguage('en');

// console.log("translations loaded");
export default i18n;