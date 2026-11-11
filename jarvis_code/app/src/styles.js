import { StyleSheet } from "react-native";

export const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, paddingTop: 60 },
  status: { fontSize: 16, fontWeight: "600", marginBottom: 8 },
  partial: { fontStyle: "italic", color: "#888", marginBottom: 8, minHeight: 20 },
  log: { flex: 1, marginBottom: 12 },
  lineYou: { marginVertical: 4, color: "#444" },
  lineBot: { marginVertical: 4, fontWeight: "600" },
  row: { flexDirection: "row", justifyContent: "space-around", marginBottom: 12 },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginVertical: 10 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 8 },
});
