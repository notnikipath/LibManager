import React from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";

export default function App() {
  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>LibManager Reader App</Text>
        <Text style={styles.subtitle}>Mobile profile, loans, reservations and e-book reading.</Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>My Loans</Text>
          <Text style={styles.cardText}>- Clean Architecture (due: 2026-05-28)</Text>
          <Text style={styles.cardText}>- Python for Data Analysis (digital)</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Reservations</Text>
          <Text style={styles.cardText}>- MAT-PRINT-001 | status: ready</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>E-Book Reader</Text>
          <Text style={styles.cardText}>DRM-enabled preview via gateway workflow.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#f2f7ea",
  },
  content: {
    padding: 20,
    gap: 14,
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#1a2c34",
  },
  subtitle: {
    fontSize: 15,
    color: "#52606b",
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#dbe5d1",
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#1f2f37",
    marginBottom: 6,
  },
  cardText: {
    fontSize: 14,
    color: "#50606a",
    marginBottom: 4,
  },
});
