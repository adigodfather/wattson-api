// ─── Netopia mobilPay v1 — criptare/decriptare (modul crypto nativ Node) ────
// Cerere: AES-256-CBC pt. XML + RSA (PKCS#1 v1.5) pt. cheia AES (echivalent openssl_seal).
// IPN: invers, cu cheia privată. NU loga niciodată cheile sau XML-ul în clar.
import crypto from "crypto";
import { getNetopiaConfig } from "./config";

export interface SealedRequest {
  env_key: string; // cheia AES, criptată RSA cu public.cer, base64
  data: string;    // XML-ul, criptat AES-256-CBC, base64
  cipher: string;  // "aes-256-cbc"
  iv: string;      // IV-ul AES, base64
}

const CIPHER = "aes-256-cbc";

/** Criptează XML-ul cererii pentru Netopia. Întoarce câmpurile env_key/data/cipher/iv. */
export function encryptRequest(xml: string): SealedRequest {
  const cfg = getNetopiaConfig();
  const aesKey = crypto.randomBytes(32); // AES-256
  const iv = crypto.randomBytes(16);

  const cipher = crypto.createCipheriv(CIPHER, aesKey, iv);
  const data = Buffer.concat([cipher.update(xml, "utf8"), cipher.final()]);

  // public.cer e un certificat X.509 -> extragem cheia publică pt. encrypt.
  const pubKey = crypto.createPublicKey(cfg.publicCer);
  const env_key = crypto.publicEncrypt(
    { key: pubKey, padding: crypto.constants.RSA_PKCS1_PADDING },
    aesKey
  );

  return {
    env_key: env_key.toString("base64"),
    data: data.toString("base64"),
    cipher: CIPHER,
    iv: iv.toString("base64"),
  };
}

/** Decriptează un IPN primit de la Netopia (env_key/data/cipher/iv) -> XML. */
export function decryptIpn(env_key: string, data: string, cipher: string, iv: string): string {
  const cfg = getNetopiaConfig();
  const privKey = crypto.createPrivateKey(cfg.privateKey);
  const aesKey = crypto.privateDecrypt(
    { key: privKey, padding: crypto.constants.RSA_PKCS1_PADDING },
    Buffer.from(env_key, "base64")
  );

  const alg = (cipher || CIPHER).toLowerCase();
  const decipher = crypto.createDecipheriv(alg, aesKey, Buffer.from(iv, "base64"));
  const xml = Buffer.concat([decipher.update(Buffer.from(data, "base64")), decipher.final()]);
  return xml.toString("utf8");
}
