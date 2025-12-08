package com.yurap.securedataapp.crypto

import android.content.Context
import java.io.InputStream
import java.io.OutputStream
import javax.crypto.Cipher
import javax.crypto.CipherOutputStream
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import kotlin.random.Random

object CryptoUtils {
    private const val alias = "secure_aes_key"

    private fun getOrCreateKey(context: Context): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val entry = ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry
        if (entry != null) return entry.secretKey
        val kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        val spec = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        kg.init(spec)
        return kg.generateKey()
    }

    fun encryptStream(context: Context, input: InputStream, output: OutputStream) {
        val key = getOrCreateKey(context)
        val iv = Random.nextBytes(12)
        output.write(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        CipherOutputStream(output, cipher).use { cos ->
            input.copyTo(cos)
        }
    }

    fun encryptBytes(context: Context, bytes: ByteArray, output: OutputStream) {
        val key = getOrCreateKey(context)
        val iv = Random.nextBytes(12)
        output.write(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        CipherOutputStream(output, cipher).use { cos ->
            cos.write(bytes)
        }
    }
}
