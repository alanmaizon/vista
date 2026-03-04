let firebaseModulesPromise = null;

async function loadFirebaseModules() {
  if (!firebaseModulesPromise) {
    firebaseModulesPromise = Promise.all([
      import("https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/11.4.0/firebase-auth.js"),
    ]);
  }
  const [appModule, authModule] = await firebaseModulesPromise;
  return {
    appModule,
    authModule,
  };
}

export async function initializeFirebaseApp(config) {
  const { appModule, authModule } = await loadFirebaseModules();
  const existing = appModule.getApps()[0];
  const app = existing ?? appModule.initializeApp(config);
  const auth = authModule.getAuth(app);
  return { app, auth, authModule };
}

export async function signInWithFirebase(config, { email, password }) {
  const { auth, authModule } = await initializeFirebaseApp(config);
  if (email && password) {
    const credential = await authModule.signInWithEmailAndPassword(auth, email, password);
    return credential.user;
  }
  const credential = await authModule.signInAnonymously(auth);
  return credential.user;
}
