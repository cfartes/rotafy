import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val appDefines = (project.findProperty("dart-defines") as String?)
    ?.split(",")?.map { String(Base64.getDecoder().decode(it)).split("=", limit = 2) }
    ?.filter { it.size == 2 }?.associate { it[0] to it[1] } ?: emptyMap()

val signingProperties = Properties()
val signingFile = rootProject.file(project.findProperty("rotafySigningFile") as String? ?: "key.properties")
if (signingFile.exists()) signingFile.inputStream().use { signingProperties.load(it) }
if (gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) } && !signingFile.exists()) {
    throw GradleException("Configure a assinatura release em key.properties antes de compilar.")
}

android {
    namespace = "br.com.nexusdataanalytics.nexus_rotafy"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = appDefines["APP_ID"] ?: "br.com.nexusdataanalytics.nexus_rotafy"
        manifestPlaceholders["appLabel"] = appDefines["APP_NAME"] ?: "Nexus Rotafy"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = maxOf(23, flutter.minSdkVersion)
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (signingFile.exists()) {
                keyAlias = signingProperties.getProperty("keyAlias")
                keyPassword = signingProperties.getProperty("keyPassword")
                storeFile = file(signingProperties.getProperty("storeFile"))
                storePassword = signingProperties.getProperty("storePassword")
            }
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
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

dependencies {
    // Same location client already used by geolocator_android.
    implementation("com.google.android.gms:play-services-location:21.2.0")
}
