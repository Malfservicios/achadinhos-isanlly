// App de Android dos Achadinhos: uma «Trusted Web Activity» que abre o painel
// (malfservicios.github.io/achadinhos-isanlly) em tela cheia usando o Chrome por dentro.
// Qualquer mudanca no painel aparece no app sem reinstalar.
plugins {
    id("com.android.application")
}

// O GitHub Actions passa o numero da compilacao para cada APK instalar por cima do anterior.
val buildNumber = (System.getenv("APP_VERSION_CODE") ?: "1").toInt()

android {
    namespace = "br.com.malfservicios.achadinhos"
    compileSdk = 34

    defaultConfig {
        applicationId = "br.com.malfservicios.achadinhos"
        minSdk = 21
        targetSdk = 34
        versionCode = buildNumber
        versionName = "1.0.$buildNumber"
        resValue("string", "app_name", "Achadinhos")
        resValue("string", "start_url", "https://malfservicios.github.io/achadinhos-isanlly/?app=android")
    }

    signingConfigs {
        create("release") {
            // A chave NUNCA fica no repositorio: chega pelos «Secrets» do GitHub.
            val path = System.getenv("SIGNING_KEY_PATH")
            if (path != null) {
                storeFile = file(path)
                storeType = "pkcs12"
                storePassword = System.getenv("SIGNING_PASSWORD")
                keyAlias = System.getenv("SIGNING_KEY_ALIAS")
                keyPassword = System.getenv("SIGNING_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.google.androidbrowserhelper:androidbrowserhelper:2.5.0")
    implementation("androidx.browser:browser:1.8.0")
}
