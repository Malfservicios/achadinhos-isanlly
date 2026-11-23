package br.com.malfservicios.achadinhos;

import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;

import androidx.browser.customtabs.CustomTabColorSchemeParams;
import androidx.browser.trusted.TrustedWebActivityIntentBuilder;

import com.google.androidbrowserhelper.trusted.TwaLauncher;

/**
 * Abre o painel em tela cheia (Trusted Web Activity), de preferencia com o Chrome:
 * assim o botao "Compartilhar no WhatsApp" envia foto/video junto com o texto.
 */
public class MainActivity extends Activity {

    private static final String[] PREFERRED = {
            "com.android.chrome", "com.chrome.beta", "com.chrome.dev", "com.chrome.canary"
    };

    private TwaLauncher launcher;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int bg = Color.parseColor("#2A180E");
        Uri url = Uri.parse(getString(R.string.start_url));

        TrustedWebActivityIntentBuilder builder = new TrustedWebActivityIntentBuilder(url)
                .setDefaultColorSchemeParams(new CustomTabColorSchemeParams.Builder()
                        .setToolbarColor(bg)
                        .setNavigationBarColor(bg)
                        .build());

        launcher = new TwaLauncher(this, pickChrome());
        launcher.launch(builder, null, null, this::finish);
    }

    private String pickChrome() {
        PackageManager pm = getPackageManager();
        for (String pkg : PREFERRED) {
            try {
                if (pm.getApplicationInfo(pkg, 0).enabled) {
                    return pkg;
                }
            } catch (PackageManager.NameNotFoundException ignored) {
                // nao instalado
            }
        }
        return null; // sem Chrome: navegador padrao
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (launcher != null) {
            launcher.destroy();
        }
    }
}
