import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing comes from an ignored key.properties (or the same values as
// environment variables in a secure shell). Nothing secret lives in Git.
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun signingValue(name: String, env: String): String? =
    keyProperties.getProperty(name) ?: System.getenv(env)

val releaseStoreFile = signingValue("storeFile", "KISAN_MITRA_KEYSTORE")
val hasReleaseSigning = releaseStoreFile != null &&
    signingValue("storePassword", "KISAN_MITRA_KEYSTORE_PASSWORD") != null &&
    signingValue("keyAlias", "KISAN_MITRA_KEY_ALIAS") != null &&
    signingValue("keyPassword", "KISAN_MITRA_KEY_PASSWORD") != null

android {
    namespace = "com.initio.kisanmitra"
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.initio.kisanmitra"
        minSdk = 24
        targetSdk = 35
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // OIDC redirect (flutter_appauth) for live sign-in.
        manifestPlaceholders["appAuthRedirectScheme"] = "com.initio.kisanmitra"
        manifestPlaceholders["usesCleartextTraffic"] = "false"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(releaseStoreFile!!)
                storePassword = signingValue("storePassword", "KISAN_MITRA_KEYSTORE_PASSWORD")
                keyAlias = signingValue("keyAlias", "KISAN_MITRA_KEY_ALIAS")
                keyPassword = signingValue("keyPassword", "KISAN_MITRA_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // Local development talks to http://10.0.2.2.
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            // Without a release key the release build stays unsigned rather
            // than silently falling back to the shared debug key.
            signingConfig = if (hasReleaseSigning) signingConfigs.getByName("release") else null
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
