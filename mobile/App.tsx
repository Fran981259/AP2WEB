import { useState } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, TextInput, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { login } from './src/api';
import { colors, spacing } from './src/theme';

export default function App() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    setMessage('');
    try {
      const user = await login(username.trim(), password);
      setMessage(`Olá, ${user.username}. Sessão iniciada.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Não foi possível entrar.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      <View style={styles.card}>
        <Text style={styles.brand}>AP2WEB</Text>
        <Text style={styles.title}>Entrar</Text>
        <TextInput autoCapitalize="none" placeholder="Usuário" placeholderTextColor={colors.muted} value={username} onChangeText={setUsername} style={styles.input} />
        <TextInput secureTextEntry placeholder="Senha" placeholderTextColor={colors.muted} value={password} onChangeText={setPassword} style={styles.input} />
        <Pressable disabled={loading} onPress={handleLogin} style={styles.button}>
          {loading ? <ActivityIndicator color={colors.text} /> : <Text style={styles.buttonText}>Entrar</Text>}
        </Pressable>
        {!!message && <Text style={styles.message}>{message}</Text>}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', padding: spacing.lg },
  card: { backgroundColor: colors.surface, borderRadius: 16, padding: spacing.lg },
  brand: { color: colors.primary, fontSize: 18, fontWeight: '700', marginBottom: spacing.lg },
  title: { color: colors.text, fontSize: 28, fontWeight: '700', marginBottom: spacing.lg },
  input: { backgroundColor: colors.background, borderRadius: 10, color: colors.text, fontSize: 16, marginBottom: spacing.md, padding: spacing.md },
  button: { alignItems: 'center', backgroundColor: colors.primary, borderRadius: 10, minHeight: 48, justifyContent: 'center', padding: spacing.md },
  buttonText: { color: colors.text, fontSize: 16, fontWeight: '700' },
  message: { color: colors.muted, fontSize: 15, marginTop: spacing.md },
});
